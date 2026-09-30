"""STORM PS4 PKG SENDER - DirectPackageInstaller Payload Protocol Module.

Handles payload injection to PS4 port 9090 (PyLoader / BinLoader / GoldHEN)
and reverse TCP socket communication for native BGFT installations with on-screen
custom Title and Icon0 notifications.
"""

import os
import sys
import socket
import struct
import threading
import time
from typing import Optional, Callable, Dict, Any

PAYLOAD_MARKER = b"\xb4\xb4\xb4\xb4\xb4\xb4"


def get_local_ip_for_remote(remote_ip: str) -> str:
    """Determine the LAN IP of this PC used to reach the PS4."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((remote_ip, 9090))
        local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        # Fallback to general hostname
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        s.close()


def check_goldhen_binloader(ps4_ip: str, timeout: float = 3.0) -> bool:
    """Check if PS4 BinLoader / PyLoader is listening on port 9090."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ps4_ip, 9090))
        s.close()
        return True
    except Exception:
        return False


def get_payload_path() -> Optional[str]:
    """Find the path to ps4-pkg-installer.bin."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ps4-pkg-installer.bin"),
        os.path.join(os.getcwd(), "tools", "ps4-pkg-installer.bin"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps4-pkg-installer.bin"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


class PayloadSession:
    """Manages an active reverse-TCP session with the PS4 payload."""

    def __init__(self, ps4_ip: str, log_callback: Optional[Callable[[str, str], None]] = None):
        self.ps4_ip = ps4_ip
        self.log = log_callback or (lambda msg, lvl: print(f"[{lvl}] {msg}"))
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.listen_port: int = 0
        self.local_ip: str = ""
        self.is_connected = False
        self._lock = threading.Lock()

    def start_session(self, timeout: float = 15.0) -> bool:
        """Start listening, patch payload, inject into PS4:9090, and wait for callback."""
        payload_path = get_payload_path()
        if not payload_path:
            self.log("Payload binary tools/ps4-pkg-installer.bin not found!", "ERROR")
            return False

        with open(payload_path, "rb") as f:
            payload_data = bytearray(f.read())

        offset = payload_data.find(PAYLOAD_MARKER)
        if offset < 0:
            self.log("Invalid payload format: marker B4 B4 B4 B4 B4 B4 not found", "ERROR")
            return False

        self.local_ip = get_local_ip_for_remote(self.ps4_ip)

        # Open dynamic TCP server port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", 0))
        self.server_socket.listen(1)
        self.server_socket.settimeout(timeout)
        self.listen_port = self.server_socket.getsockname()[1]

        # Patch IP (4 bytes) and Port (2 bytes Big Endian) into payload
        ip_parts = [int(p) for p in self.local_ip.split(".")]
        for i, b in enumerate(ip_parts):
            payload_data[offset + i] = b
        struct.pack_into(">H", payload_data, offset + 4, self.listen_port)

        self.log(
            f"Injecting payload to {self.ps4_ip}:9090 (Callback: {self.local_ip}:{self.listen_port})...",
            "INFO",
        )

        # Send patched payload to PS4:9090
        try:
            s_inj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s_inj.settimeout(5.0)
            s_inj.connect((self.ps4_ip, 9090))
            s_inj.sendall(payload_data)
            s_inj.close()
            self.log("Payload binary successfully sent to PS4 port 9090. Awaiting callback...", "INFO")
        except Exception as e:
            self.log(f"Failed to inject payload to {self.ps4_ip}:9090: {e}", "ERROR")
            self.close()
            return False

        # Wait for incoming connection from PS4 payload
        try:
            client, addr = self.server_socket.accept()
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.client_socket = client
            self.is_connected = True
            self.log(f"PS4 Payload successfully connected from {addr[0]}:{addr[1]}!", "INFO")
            return True
        except socket.timeout:
            self.log("PS4 Payload did not connect back within timeout (15s). Check firewall.", "ERROR")
            self.close()
            return False
        except Exception as e:
            self.log(f"Error awaiting PS4 payload callback: {e}", "ERROR")
            self.close()
            return False

    def send_package_job(
        self,
        url: str,
        title: str,
        content_id: str,
        category: str = "GAME",
        size_bytes: int = 0,
        icon_bytes: Optional[bytes] = None,
    ) -> bool:
        """Send installation command packet to the active PS4 payload."""
        with self._lock:
            if not self.is_connected or not self.client_socket:
                self.log("Cannot send job: Payload is not connected.", "ERROR")
                return False

            try:
                # Format:
                # Command: uint32 LE (1 = install)
                # URL: uint32 LE length + utf8 string
                # Title: uint32 LE length + utf8 string
                # ContentID: uint32 LE length + utf8 string
                # ContentType: uint32 LE length + utf8 string
                # Size: uint64 LE (bytes)
                # Icon: uint32 LE length + raw PNG bytes

                c_type = "PS4GD"
                cat_lower = category.lower()
                if "patch" in cat_lower or "update" in cat_lower:
                    c_type = "PS4GP"
                elif "dlc" in cat_lower or "addcont" in cat_lower:
                    c_type = "PS4AC"
                elif "theme" in cat_lower:
                    c_type = "PS4SD"

                packet = bytearray()
                # 1. Command
                packet.extend(struct.pack("<I", 1))

                # 2. Helper for string chunks
                def append_str(val: str):
                    encoded = val.encode("utf-8")
                    packet.extend(struct.pack("<I", len(encoded)))
                    packet.extend(encoded)

                append_str(url)
                append_str(title or "PS4 Application")
                append_str(content_id or "IV0000-CUSA00000_00-0000000000000000")
                append_str(c_type)

                # 3. Size (uint64 LE)
                packet.extend(struct.pack("<Q", max(0, int(size_bytes))))

                # 4. Icon
                icon_data = icon_bytes or b""
                packet.extend(struct.pack("<I", len(icon_data)))
                if icon_data:
                    packet.extend(icon_data)

                self.client_socket.sendall(packet)
                self.log(f"Payload install command sent: «{title}» ({content_id}) -> {url}", "INFO")
                return True

            except Exception as e:
                self.log(f"Failed to send install command over payload session: {e}", "ERROR")
                self.is_connected = False
                return False

    def close(self):
        """Close active session and sockets."""
        self.is_connected = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
