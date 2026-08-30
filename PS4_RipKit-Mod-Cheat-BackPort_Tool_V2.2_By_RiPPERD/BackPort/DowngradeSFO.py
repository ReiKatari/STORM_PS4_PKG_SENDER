#!/usr/bin/env python2.7
# (c) flatz

import sys, os, struct
import argparse
import re

def align_up(x, alignment):
	return (x + (alignment - 1)) & ~(alignment - 1)

def align_down(x, alignment):
	return x & ~(alignment - 1)

def check_file_magic(f, expected_magic):
	old_offset = f.tell()
	try:
		magic = f.read(len(expected_magic))
	except:
		return False
	finally:
		f.seek(old_offset)
	return magic == expected_magic

def read_cstring(f):
	s = ''
	while True:
		c = f.read(1)
		if not c:
			return False
		if c == '\0':
			break
		s += c
	return s

def check_sdk_version(sdk_version):
	if len(sdk_version) != 10:
		return False
	parts = sdk_version.split('.', 2)
	if len(parts) != 3:
		return False
	try:
		lengths = [2, 3, 3]
		for i, n in enumerate(parts):
			if len(n) != lengths[i]:
				return False
			n = int(n, 10)
	except:
		return False
	return True

# SDK version have 001 in "patch" field
def parse_sdk_version(sdk_version):
	major, minor, patch = sdk_version >> 24, (sdk_version >> 12) & 0xFFF, sdk_version & 0xFFF
	return major, minor, patch

def stringify_sdk_version(major, minor, patch):
	return '{0:02x}.{1:03x}.{2:03x}'.format(major, minor, patch)

def unstringify_sdk_version(sdk_version):
	major, minor, patch = map(lambda x: int(x, 16), sdk_version.split('.', 2))
	return major, minor, patch

def build_sdk_version(major, minor, patch):
	sdk_version = ((major & 0xFF) << 24) | ((minor & 0xFFF) << 12) | (patch & 0xFFF)
	return sdk_version

class SfoFile(object):
	FMT = '<4sIIII'

	MAGIC = '\x00PSF'

	FMT_STRING_SPECIAL = 0x004
	FMT_STRING         = 0x204
	FMT_UINT32         = 0x404

	class Entry(object):
		FMT = '<HHIII'

		def __init__(self):
			self.key_offset = None
			self.format = None
			self.size = None
			self.max_size = None
			self.data_offset = None

			self.key = None
			self.value = None

		def load(self, f):
			data = f.read(struct.calcsize(SfoFile.Entry.FMT))
			if len(data) != struct.calcsize(SfoFile.Entry.FMT):
				print('error: unable to read entry')
				return False

			self.key_offset, self.format, self.size, self.max_size, self.data_offset = struct.unpack(SfoFile.Entry.FMT, data)

			return True

		def save(self, f):
			data = struct.pack(SfoFile.Entry.FMT, self.key_offset, self.format, self.size, self.max_size, self.data_offset)
			if len(data) != struct.calcsize(SfoFile.Entry.FMT):
				print('error: unable to save entry')
				return False
			f.write(data)

			return True

	def __init__(self):
		self.start_offset = None
		self.magic = None
		self.version = None
		self.key_table_offset = None
		self.data_table_offset = None
		self.num_entries = None
		self.entries = None
		self.entry_map = None

	def check(self, f):
		old_offset = f.tell()
		try:
			result = check_file_magic(f, SfoFile.MAGIC)
		except:
			return False
		finally:
			f.seek(old_offset)
		return result

	def load(self, f):
		self.start_offset = f.tell()

		data = f.read(struct.calcsize(SfoFile.FMT))
		if len(data) != struct.calcsize(SfoFile.FMT):
			print('error: unable to read header')
			return False

		self.magic, self.version, self.key_table_offset, self.data_table_offset, self.num_entries = struct.unpack(SfoFile.FMT, data)
		self.entries = []
		for i in xrange(self.num_entries):
			entry = SfoFile.Entry()
			if not entry.load(f):
				return False
			assert entry.max_size >= entry.size
			self.entries.append(entry)

		self.entry_map = {}
		for i, entry in enumerate(self.entries):
			f.seek(self.start_offset + self.key_table_offset + entry.key_offset)
			entry.key = read_cstring(f)
			f.seek(self.start_offset + self.data_table_offset + entry.data_offset)
			entry.value = f.read(entry.max_size)
			entry.value = entry.value[:entry.size]
			self.entry_map[entry.key] = entry

		return True

	def fixup(self):
		self.num_entries = len(self.entries)

		self.key_table_offset = struct.calcsize(SfoFile.FMT)
		self.key_table_offset += self.num_entries * struct.calcsize(SfoFile.Entry.FMT)
		offset = 0
		for i, entry in enumerate(self.entries):
			entry.key_offset = offset
			offset += len(entry.key) + 1

		self.data_table_offset = self.key_table_offset + align_up(offset, 0x4)
		offset = 0
		for i, entry in enumerate(self.entries):
			entry.data_offset = offset
			assert len(entry.value) <= entry.max_size
			offset += entry.max_size

	def save(self, f):
		data = struct.pack(SfoFile.FMT, self.magic, self.version, self.key_table_offset, self.data_table_offset, self.num_entries)
		if len(data) != struct.calcsize(SfoFile.FMT):
			print('error: unable to save header')
			return False
		f.write(data)

		for i, entry in enumerate(self.entries):
			if not entry.save(f):
				return False

		for i, entry in enumerate(self.entries):
			f.seek(self.start_offset + self.key_table_offset + entry.key_offset)
			data = entry.key + '\0'
			f.write(data)
			f.seek(self.start_offset + self.data_table_offset + entry.data_offset)
			data = entry.value.ljust(entry.max_size, '\0')
			f.write(data)

		return True

	def get_entry(self, key):
		return self.entry_map[key] if key in self.entry_map else None

	def dump(self):
		for i, entry in enumerate(self.entries):
			assert entry.format in [SfoFile.FMT_STRING_SPECIAL, SfoFile.FMT_STRING, SfoFile.FMT_UINT32]
			if entry.format == SfoFile.FMT_STRING_SPECIAL:
				value = entry.value[:entry.size]
			elif entry.format == SfoFile.FMT_STRING:
				value = entry.value[:entry.size - 1]
			elif entry.format == SfoFile.FMT_UINT32:
				assert entry.size in [1, 2, 4, 8]
				if entry.size == struct.calcsize('B'):
					value = '0x{0:02X}'.format(struct.unpack('<B', entry.value)[0])
				elif entry.size == struct.calcsize('H'):
					value = '0x{0:04X}'.format(struct.unpack('<H', entry.value)[0])
				elif entry.size == struct.calcsize('I'):
					value = '0x{0:08X}'.format(struct.unpack('<I', entry.value)[0])
				elif entry.size == struct.calcsize('Q'):
					value = '0x{0:016X}'.format(struct.unpack('<Q', entry.value)[0])
			print('{0} = {1}'.format(entry.key, value))

class MyParser(argparse.ArgumentParser):
	def error(self, message):
		self.print_help()
		sys.stderr.write('\nerror: {0}\n'.format(message))
		sys.exit(2)

parser = MyParser(description='sfo tool')
parser.add_argument('input', type=str, help='old file')
parser.add_argument('output', type=str, help='new file')
parser.add_argument('--verbose', action='store_true', default=False, help='show details')
parser.add_argument('--dump', action='store_true', default=False, help='dump entries')
parser.add_argument('--sdk-version', type=str, default=None, help='needed sdk version')
parser.add_argument('--system-version', type=str, default=None, help='needed sdk version')

if len(sys.argv) == 1:
	parser.print_usage()
	sys.exit(1)

args = parser.parse_args()

input_file_path = args.input
if not os.path.isfile(input_file_path):
	parser.error('invalid input file: {0}'.format(input_file_path))

output_file_path = args.output
if os.path.exists(output_file_path) and not os.path.isfile(output_file_path):
	parser.error('invalid output file: {0}'.format(output_file_path))

if args.sdk_version and not check_sdk_version(args.sdk_version):
	parser.error('bad sdk version')
if args.system_version and not check_sdk_version(args.system_version):
	parser.error('bad system version')

if args.verbose:
	print('reading sfo file: {0}'.format(input_file_path))
with open(input_file_path, 'rb') as f:
	sfo = SfoFile()
	if not sfo.check(f):
		print('error: invalid sfo file format')
		sys.exit(1)
	if not sfo.load(f):
		print('error: unable to load sfo file')
		sys.exit(1)

if args.sdk_version is not None and 'PUBTOOLINFO' in sfo.entry_map:
	entry = sfo.entry_map['PUBTOOLINFO']
	assert entry.format == SfoFile.FMT_STRING
	sdk_ver_regexp = re.compile(r'sdk_ver=(\d{8})')
	matches = sdk_ver_regexp.search(entry.value)
	if matches is not None:
		start_pos, end_pos = matches.span(1)
		old_sdk_version = int(entry.value[start_pos:end_pos], 16)
		major, minor, patch = parse_sdk_version(old_sdk_version)
		old_sdk_version_str = stringify_sdk_version(major, minor, patch)
		if args.verbose:
			print('sdk version: {0}'.format(old_sdk_version_str))
		major, minor, patch = unstringify_sdk_version(args.sdk_version)
		new_sdk_version = build_sdk_version(major, minor, patch)
		new_sdk_version_str = stringify_sdk_version(major, minor, patch)
		if old_sdk_version > new_sdk_version:
			print('fixing sdk version...')
			if args.verbose:
				print('wanted sdk version: {0}'.format(new_sdk_version_str))
			new_sdk_version = '{0:08X}'.format(new_sdk_version)
			assert len(new_sdk_version) == (end_pos - start_pos)
			entry.value = entry.value[:start_pos] + new_sdk_version + entry.value[end_pos:]

if args.system_version is not None and 'SYSTEM_VER' in sfo.entry_map:
	if not check_sdk_version(args.system_version):
		parser.error('error: bad sdk version')
	entry = sfo.entry_map['SYSTEM_VER']
	assert entry.format == SfoFile.FMT_UINT32 and entry.size == struct.calcsize('I')
	old_system_version, = struct.unpack('<I', entry.value)
	major, minor, patch = parse_sdk_version(old_system_version)
	old_system_version_str = stringify_sdk_version(major, minor, patch)
	if args.verbose:
		print('system version: {0}'.format(old_system_version_str))
	major, minor, patch = unstringify_sdk_version(args.system_version)
	new_system_version = build_sdk_version(major, minor, patch)
	new_system_version_str = stringify_sdk_version(major, minor, patch)
	if old_system_version > new_system_version:
		print('fixing system version...')
		if args.verbose:
			print('wanted system version: {0}'.format(new_system_version_str))
		entry.value = struct.pack('<I', new_system_version)

if args.verbose:
	print('recalculating offsets...')
sfo.fixup()

if args.dump:
	print('dumping entries...')
	sfo.dump()

if args.verbose:
	print('writing sfo file: {0}'.format(output_file_path))
with open(output_file_path, 'wb') as f:
	if not sfo.save(f):
		print('error: unable to save sfo file')
		sys.exit(1)

if args.verbose:
	print('done')