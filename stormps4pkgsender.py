import sys
import os
import stat
import time
import socket
import threading
import struct
import re
import random
import datetime
import ctypes
import requests
import urllib.parse
import io
import json
import ftplib
import psutil
import subprocess
import shutil
import shlex
import tempfile
import winreg
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLineEdit, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QLabel, QFileDialog, QProgressBar, 
    QGridLayout, QHeaderView, QMessageBox, QAbstractItemView, QMenu,
    QTreeWidgetItemIterator, QFrame, QCheckBox, QComboBox,
    QStyleFactory, QToolButton, QStyledItemDelegate, QDialog,
    QSpinBox, QFormLayout, QDialogButtonBox, QGroupBox,
    QSizePolicy, QSystemTrayIcon, QStackedWidget, QSplitter, QStyle, QInputDialog,
    QTableWidget, QTableWidgetItem, QProgressDialog
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, QObject, QTimer, QSize, QThread, QMutex, QRect, QUrl, QEvent
from PyQt6.QtGui import (
    QColor, QBrush, QAction, QGuiApplication, QCursor, QPen, 
    QPalette, QGradient, QLinearGradient, QIcon, QPixmap, 
    QDesktopServices, QDrag, QShortcut, QKeySequence, QFont
)


CURRENT_VERSION = "1.2.84"
GITHUB_REPO = "ReiKatari/STORM_PS4_PKG_SENDER"

try:
    myappid = 'STORM.PS4Sender.Final.v1273'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

# --- GLOBAL LOG BUFFER ---
LOG_BUFFER = deque(maxlen=500)  # Keep last 500 log entries
LOG_LOCK = threading.Lock()

def log(msg, level="INFO"):
    """Add timestamped log entry to global buffer and print to console."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] {msg}") # Always print to console/stdout

def perform_cleanup(settings_val):
    """Standalone cleanup function to be called on exit."""
    debug_log = []
    app_path = "UNKNOWN"
    def dlog(msg):
        debug_log.append(f"[{datetime.datetime.now()}] {msg}")
        
    dlog("=== EXIT CLEANUP START (Standalone) ===")
    
    try:
        dlog(f"Setting 'cleanup_backports': {settings_val}")
        
        if settings_val:
            # Robust Root Drive Detection
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
                dlog(f"Mode: FROZEN (EXE). Path: {app_path}")
            else:
                app_path = os.path.abspath(__file__)
                dlog(f"Mode: SCRIPT. Path: {app_path}")
                
            drive_root = os.path.splitdrive(app_path)[0]
            dlog(f"Calculated Drive Root: {drive_root}")
            
            if not drive_root: 
                drive_root = "C:"
                dlog("Drive Root was empty, defaulting to C:")
                
            if not drive_root.endswith(os.sep): drive_root += os.sep
            temp_bp_root = os.path.join(drive_root, "STORM_BP_TEMP")
            dlog(f"Target Cleanup Path: {temp_bp_root}")
            
            try:
                check_exists = os.path.exists(temp_bp_root)
                dlog(f"os.path.exists check = {check_exists}")
            except Exception as e:
                dlog(f"os.path.exists FAILED: {e}")
                check_exists = False
            
            if check_exists:
                dlog(f"Folder FOUND. Attempting delete...")
                
                # 1. Kill tools
                try:
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['name'] in ['orbis-pub-cmd.exe', 'orbis-pub-sfo.exe']:
                            try: 
                                name = proc.info['name']
                                dlog(f"Killing process: {name} (PID: {proc.info['pid']})")
                                proc.kill()
                                try: 
                                    proc.wait(timeout=2)
                                    dlog(f"Process {name} terminated.")
                                except: 
                                    dlog(f"Wait timeout for {name}")
                            except Exception as kill_err: 
                                dlog(f"Kill failed for {name}: {kill_err}")
                except Exception as ps_err: 
                     dlog(f"Process iteration failed: {ps_err}")
                
                # 2. Define Error Handler
                def on_rm_error(func, path, exc_info):
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                        dlog(f"Cleared Read-Only (Retry Success): {path}")
                    except Exception as ro_err:
                        dlog(f"Failed to clear Read-Only {path}: {ro_err}")

                # 3. Retry Loop
                success = False
                for attempt in range(3):
                    try:
                        dlog(f"RMtree Attempt {attempt+1}")
                        shutil.rmtree(temp_bp_root, onerror=on_rm_error)
                        if not os.path.exists(temp_bp_root):
                            dlog("Success! Folder deleted.")
                            success = True
                            break
                        else:
                            dlog("Folder still exists after rmtree return.")
                    except Exception as e:
                        dlog(f"RMtree Exception: {e}")
                        time.sleep(0.5)
                        
                if not success:
                    dlog("!!! FINAL FAILURE: Folder still exists !!!")
                    # FLUSH LOG TO FILE (Only on failure)
                    if "app_path" not in locals() or app_path == "UNKNOWN":
                        if getattr(sys, 'frozen', False): app_path = sys.executable
                        else: app_path = os.path.abspath(__file__)
                    log_dir = os.path.dirname(app_path)
                    log_file = os.path.join(log_dir, "cleanup_debug.txt")
                    try:
                        with open(log_file, "w", encoding="utf-8") as f: f.write("\n".join(debug_log))
                    except: pass

            else:
                dlog("Target folder not found (already deleted?)")
        else:
            dlog("Cleanup SKIPPED (Setting is disabled)")

    except Exception as e:
        dlog(f"CRITICAL CLEANUP EXCEPTION: {e}")
        # FLUSH LOG TO FILE (Critical Error)
        if "app_path" not in locals() or app_path == "UNKNOWN":
             if getattr(sys, 'frozen', False): app_path = sys.executable
             else: app_path = os.path.abspath(__file__)
        log_dir = os.path.dirname(app_path)
        log_file = os.path.join(log_dir, "cleanup_debug.txt")
        try:
             with open(log_file, "w", encoding="utf-8") as f: f.write("\n".join(debug_log))
        except: pass
    
    dlog("=== EXIT CLEANUP END ===")
    entry = f"[{timestamp}] [{level}] {msg}"
    with LOG_LOCK:
        LOG_BUFFER.append(entry)
    # Filter out noisy logs from console
    if level in ["INFO", "WARN", "ERROR"]:
        print(entry)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0: ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception as e: 
        log(f"hide_console error: {e}", "WARN")



def get_pkg_info_from_sfo(data):
    """Parse raw SFO data and return a dictionary of keys/values."""
    info = {}
    try:
        magic = data[:4]
        if magic != b"\x00PSF": return info
        
        key_table_start = struct.unpack_from("<I", data, 0x08)[0]
        data_table_start = struct.unpack_from("<I", data, 0x0C)[0]
        entries_count = struct.unpack_from("<I", data, 0x10)[0]
        
        for i in range(entries_count):
            offset = 0x14 + (i * 16)
            key_offset = struct.unpack_from("<H", data, offset)[0]
            data_fmt = struct.unpack_from("<H", data, offset + 2)[0]
            data_len = struct.unpack_from("<I", data, offset + 4)[0]
            data_max_len = struct.unpack_from("<I", data, offset + 8)[0]
            data_offset = struct.unpack_from("<I", data, offset + 12)[0]
            
            key_addr = key_table_start + key_offset
            key_end = data.find(b"\x00", key_addr)
            if key_end == -1: key_end = len(data)
            key = data[key_addr:key_end].decode("utf-8", errors="ignore")
            
            val_addr = data_table_start + data_offset
            val_data = data[val_addr:val_addr+data_len]
            
            # Formats: 0x0404=int, 0x0204=utf8, 0x0004=utf8_special
            val = ""
            if data_fmt in [0x0204, 0x0004]:
                val = val_data.decode("utf-8", errors="ignore").rstrip("\x00")
            elif data_fmt == 0x0404:
                val = str(struct.unpack("<I", val_data)[0])
            else:
                val = str(val_data)
            
            info[key.upper()] = val
            # log(f"SFO Key: {key} -> {val}", "DEBUG")
    except Exception as e:
        log(f"SFO Parse Error: {e}", "WARN")
    return info
# --- UTILS ---
class CenterDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter

class ImagePreviewDialog(QDialog):
    def __init__(self, parent, image_data, title="Preview"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)
        
        lbl_img = QLabel()
        pix = QPixmap()
        pix.loadFromData(image_data)
        if not pix.isNull():
            # Resize if too large
            screen = QApplication.primaryScreen().size()
            if pix.width() > screen.width() * 0.8 or pix.height() > screen.height() * 0.8:
                pix = pix.scaled(screen.width() * 0.8, screen.height() * 0.8, Qt.AspectRatioMode.KeepAspectRatio)
            lbl_img.setPixmap(pix)
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl_img)
            self.resize(pix.size() + QSize(40, 60))
        else:
            layout.addWidget(QLabel("Failed to load image"))

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

# --- LOCALIZATION ---
LOCALE = {
    "ru": {
        "window_title": f"STORM PS4 PKG SENDER v{CURRENT_VERSION}",
        "ps4_ip": "PS4 IP:",
        "check_conn": "🔗 Проверить",
        "scan_net": "🌐 Поиск",
        "overwrite": "Перезапись",
        "confirm_uninstall": "Подтверждение удаления",
        "msg_confirm_uninstall": "Удалить {} ({})?",
        "hide_pinned": "Скрыть закрепленное",
        "large_font": "Крупный шрифт",
        "backup_btn": "💾 Бэкап",
        "restore_btn": "♻ Восстановление бэкапа", 
        "btn_add_main": "➕ Добавить",
        "menu_add_files": "📄 Файлы (.pkg / .bin)",
        "menu_add_folder": "📁 Папку",
        "col_file": "Файл / Путь",
        "col_tid": "ID / Тип",
        "col_ver": "Версия",
        "col_size": "Размер",
        "col_region": "Регион",
        "col_category": "Категория",
        "col_speed": "Скорость",
        "col_prog": "Прогресс",
        "col_status": "Статус",
        "col_act": "Действия",
        "collapse": "🔼 Свернуть все",
        "expand": "🔽 Развернуть все",
        "pause_global": "⏸ Пауза все",
        "resume_global": "▶ Продолжить все",
        "cancel_all": "✖ Отменить все",
        "install_all": "🚀 Отправить все",
        "waiting": "Ожидание...",
        "ready": "Готов к работе",
        "server_off": "Сервер: Выкл",
        "server_ok": "Сервер: {} (OK)",
        "server_err": "Ошибка сервера",
        "status_offline": "Не в сети",
        "status_rpi_full": "В сети (RPI, FTP, BinLoader)",
        "status_sppi_full": "В сети (SPPI, FTP, BinLoader)",
        "status_ftp_bin": "В сети (FTP и BinLoader)",
        "status_ftp_only": "В сети (Только FTP)",
        "status_bin_only": "В сети (Только BinLoader)",
        "checking": "Проверка...",
        "installing": "Установка...",
        "sending_bin": "Отправка пейлоада...",
        "paused": "Пауза",
        "error": "Ошибка",
        "cancelled": "Отменено",
        "installed": "Установлено",
        "sent_payload": "Пейлоад отправлен",
        "already": "Ранее установлено",
        "sent": "Ссылка принята",
        "not_installed": "Не установлено",
        "queue_paused": "⏸ Очередь приостановлена",
        "queue_resumed": "▶ Очередь возобновлена",
        "scan_start": "🔍 Поиск PS4 в сети...",
        "scan_found": "✅ Найдено PS4: {}",
        "scan_fail": "❌ PS4 не найдена в сети",
        "install_sel": "Отправить выделенные ({})",
        "pin": "📌 Закрепить",
        "unpin": "❌ Открепить",
        "pin_sel": "📌 Закрепить выделенные ({})",
        "unpin_sel": "❌ Открепить выделенные ({})",
        "remove_list": "Убрать из списка",
        "copy": "📋 {} скопировано!",
        "done": "Завершено",
        "sending": "Отправка {}%",
        "skipped_no_space": "Пропущен, нет места",
        "busy": "PS4 занята (Busy)",
        "timeout": "Тайм-аут соединения",
        "frozen": "RPI завис? Перезагрузите PS4 App",
        "bkp_title": "Настройки бэкапа сохранений",
        "bkp_grp": "Автоматическое резервное копирование (FTP)",
        "bkp_enable": "Включить авто-бэкап",
        "bkp_path": "Папка для сохранений:",
        "bkp_int": "Интервал проверки:",
        "bkp_run": "▶ Запустить бэкап сейчас",
        "bkp_info": "<i>* Для работы необходим запущенный GoldHEN (порт 2121).<br>* Сохранения скачиваются в папки по дате/времени.</i>",
        "save": "Сохранить",
        "backport_tool": "Инструмент Backport",
        "backport_ctx": "🔧 Создать Backport (PKG)",
        "backport_error": "Ошибка Backport",
        "backport_config_err": "Пожалуйста, проверьте наличие orbis-pub-cmd.exe в папке tools.",
        "icon_not_found": "Иконка не найдена",
        "icon_header_err": "Иконка не найдена в заголовке",
        "icon_preview": "Просмотр иконки",
        "ftp_warning_title": "Внимание!",
        "ftp_warning_text": "Все изменения в FTP Browser вы производите на свой страх и риск!\nРазработчик не несет ответственности за удаленные системные файлы.",
        "ftp_warning_chk": "Больше не показывать",
        "rename_wide": "Новое имя файла:",
        "cancel": "Отменить",
        "rest_title": "Восстановление сохранений на PS4",
        "rest_browse": "📂 Выбрать бэкап",
        "rest_send": "Передать в PS4",
        "rest_col1": "Пользователь / Title ID",
        "rest_col2": "Путь к файлам",
        "rest_success": "✅ Восстановление завершено успешно!",
        "rest_start": "🚀 Начало восстановления...",
        "report_wait": "⏳ Завершено. Следующий через {}с...",
        "confirm_title": "Подтверждение",
        "confirm_cancel_all": "Вы действительно хотите отменить все задачи?\nОчередь будет очищена.",
        "btn_yes": "Подтвердить",
        "btn_no": "Отменить",
        "yes": "Да",
        "no": "Нет",
        "auto_update": "Авто-обновление",
        "upd_title": "Доступно обновление",
        "upd_msg": "Доступна новая версия: <b>{}</b><br>Хотите скачать и установить обновление?",
        "status_sppi_full": "В сети (SPPI)",
        "status_rpi_full": "В сети (RPI)",
        "status_ftp_bin": "В сети (FTP, BinLoader)",
        "status_ftp_only": "В сети (Только FTP)",
        "status_bin_only": "В сети (Только BinLoader)",
        "status_online": "В сети",
        "status_offline": "Не в сети",
        "upd_btn": "🚀 Обновить",
        "upd_skip": "Позже",
        "upd_no_new": "✅ Установлена последняя версия",
        "upd_err": "❌ Ошибка проверки обновлений",
        "upd_downloading": "📥 Скачивание обновления... {}%",
        "stat_total": "Всего: {} | Готово: {} | Ошибок: {}",
        "stat_size": "Размер: {} / {}",
        "stat_eta": "Осталось времени: {}",
        "tray_show": "Развернуть / Свернуть",
        "tray_exit": "Выход",
        "ctx_folder": "📂 Открыть в папке",
        "ctx_extract_icon": "🖼 Извлечь иконку",
        "ctx_rename_pkg": "✏ Переименовать PKG",
        "col_visibility": "Показать/скрыть столбцы",
        "mini_mode": "Компактный режим",
        "logs_title": "📋 Логи",
        "logs_copy": "📋 Копировать",
        "logs_clear": "🗑 Очистить",
        "logs_close": "✖ Закрыть",
        "logs_empty": "(Пока нет логов)",
        "logs_cleared": "(Логи очищены)",
        "ftp_pc": "ПК:",
        "ftp_ps4": "PS4:",
        "ftp_connect": "🔗 Подключиться",
        "ftp_disconnect": "❌ Отключиться",
        "ftp_upload": "➡ Загрузить",
        "ftp_download": "⬅ Скачать",
        "ftp_mkdir": "📁 Папка",
        "ftp_delete": "❌ Удалить",
        "ftp_name": "Имя",
        "ftp_size": "Размер",
        "ftp_date": "Дата",
        "ftp_refresh": "Обновить",
        "pkg_connect": "🔗 Подключиться",
        "pkg_refresh": "🔄 Обновить",
        "pkg_launch": "🚀 Запустить",
        "pkg_uninstall": "🗑 Удалить",
        "pkg_title": "Название",
        "pkg_tid": "Title ID",
        "pkg_ver": "Версия",
        "pkg_size": "Размер",
        "bp_title": "Инструмент Бэкпорта",
        "bp_my_list": "Свой список",
        "bp_all_fw": "Все прошивки",
        "bp_target": "Цель: {}",
        "bp_fw": "Выберите прошивку:",
        "bp_save": "Папка сохранения:",
        "bp_start": "Начать",
        "bp_browse": "Обзор",
        "ctx_change_title": "✏ Изменить отображаемое имя",
        "change_title": "Изменение имени",
        "new_title": "Новое имя:",
        "ok": "Готово",
        "cancel": "Отмена",
        "confirm_exit_text": "Закрыть программу или свернуть в трей?",
        "btn_exit": "Закрыть",
        "btn_tray": "Свернуть в трей",
        "ok": "OK",
        "cancel": "Отмена",
        "bp_pass_title": "Ввод Passcode PKG",
        "bp_pass_info": "Этот Retail PKG зашифрован уникальным паролем.\nПожалуйста, введите 32-значный passcode:",
        "bp_pass_extract": "📂 Извлечь из Base PKG (Игры)",
        "bp_pass_extract_tip": "Выберите PKG базовой игры (FPKG) для извлечения passcode",
        "bp_my_list_settings": "Свой список для бэкпорта",
        "bp_pass_select_base": "Выберите PKG базовой игры (FPKG)",
        "bp_pass_found": "✅ Passcode найден!\n{}",
        "bp_pass_not_found_title": "Не найдено",
        "bp_pass_not_found": "❌ Passcode не найден в информации о PKG.\nУбедитесь, что это FPKG или базовая игра.",
        "ftp_search_placeholder": "Поиск локально...",
        "ftp_search_placeholder_remote": "Поиск на PS4...",
        "recursive": "Рекурсивно",
        "ftp_searching": "🔎 Поиск...",
        "ctx_view_img": "🖼 Просмотр изображения",
        "ctx_rename": "✏ Переименовать",
        "ctx_new_folder": "📁 Создать папку",
        "concurrent_installs": "Одновременных установок:",
        "scan_folder": "Сканирование папки...",
        "add_files": "Добавление {} файлов...",
        "scan_dropped_folders": "Сканирование перетянутых папок...",
        "add_dropped_files": "Добавление {} перетянутых файлов..."
    },
    "en": {
        "window_title": f"STORM PS4 PKG SENDER v{CURRENT_VERSION}",
        "confirm_uninstall": "Confirm Uninstall",
        "msg_confirm_uninstall": "Uninstall {} ({})?",
        "ps4_ip": "PS4 IP:",
        "check_conn": "🔗 Check",
        "scan_net": "🌐 Scan",
        "overwrite": "Overwrite All",
        "hide_pinned": "Hide Pinned",
        "large_font": "Large Font",
        "backup_btn": "💾 Backup",
        "restore_btn": "♻ Restore Backup",
        "btn_add_main": "➕ Add",
        "menu_add_files": "📄 Files (.pkg / .bin)",
        "menu_add_folder": "📁 Folder",
        "col_file": "File / Path",
        "col_tid": "ID / Type",
        "col_ver": "Version",
        "col_size": "Size",
        "col_region": "Region",
        "col_category": "Category",
        "col_speed": "Speed",
        "col_prog": "Progress",
        "col_status": "Status",
        "col_act": "Actions",
        "collapse": "🔼 Collapse",
        "expand": "🔽 Expand",
        "pause_global": "⏸ Pause All",
        "resume_global": "▶ RESUME",
        "cancel_all": "✖ Cancel All",
        "install_all": "🚀 Send All",
        "waiting": "Waiting...",
        "ready": "Ready",
        "server_off": "Server: Off",
        "server_ok": "Server: {} (OK)",
        "server_err": "Server Error",
        "status_sppi_full": "Online (SPPI)",
        "status_rpi_full": "Online (RPI)",
        "status_ftp_bin": "Online (FTP, BinLoader)",
        "recursive": "Recursive",
        "ftp_searching": "🔎 Searching...",
        "ctx_view_img": "🖼 View Image",
        "ctx_rename": "✏ Rename",
        "ctx_new_folder": "📁 New Folder",
        "status_ftp_only": "Online (FTP Only)",
        "status_bin_only": "Online (BinLoader Only)",
        "status_online": "Online",
        "status_offline": "Offline",
        "checking": "Checking...",
        "installing": "Installing...",
        "sending_bin": "Sending payload...",
        "paused": "Paused",
        "error": "Error",
        "cancelled": "Cancelled",
        "installed": "Installed",
        "sent_payload": "Payload Sent",
        "already": "Already Installed",
        "sent": "Link Sent",
        "not_installed": "Not Installed",
        "queue_paused": "⏸ Queue Paused",
        "queue_resumed": "▶ Queue Resumed",
        "scan_start": "🔍 Scanning network...",
        "scan_found": "✅ Found PS4: {}",
        "scan_fail": "❌ PS4 not found",
        "install_sel": "Install Selected ({})",
        "pin": "📌 Pin",
        "unpin": "❌ Unpin",
        "pin_sel": "📌 Pin Selected ({})",
        "unpin_sel": "❌ Unpin Selected ({})",
        "remove_list": "Remove from list",
        "copy": "📋 {} copied!",
        "done": "Done",
        "skipped_no_space": "Skipped, no space",
        "sending": "Sending {}%",
        "busy": "PS4 Busy",
        "timeout": "Connection Timeout",
        "frozen": "RPI Frozen? Restart PS4 App",
        "bkp_title": "Save Data Backup Settings",
        "bkp_grp": "Automatic Backup (FTP)",
        "bkp_enable": "Enable Auto-Backup",
        "bkp_path": "Backup Folder:",
        "bkp_int": "Check Interval:",
        "bkp_run": "▶ Run Backup Now",
        "bkp_info": "<i>* Requires running GoldHEN (port 2121).<br>* Saves are downloaded into dated folders.</i>",
        "save": "Save",
        "rest_title": "Restore Save Data to PS4",
        "rest_browse": "📂 Browse Backup",
        "rest_send": "Send to PS4",
        "rest_col1": "User / Title ID",
        "rest_col2": "File Path",
        "rest_success": "✅ Restore completed successfully!",
        "rest_start": "🚀 Starting restore...",
        "report_wait": "⏳ File done. Next in {}s...",
        "confirm_title": "Confirmation",
        "confirm_cancel_all": "Are you sure you want to cancel all tasks?\nThe queue will be cleared.",
        "btn_yes": "Confirm",
        "btn_no": "Cancel",
        "yes": "Yes",
        "no": "No",
        "auto_update": "Auto-Update",
        "upd_title": "Update Available",
        "upd_msg": "New version found: <b>{}</b><br>Do you want to download and update now?",
        "upd_btn": "🚀 Update",
        "upd_skip": "Later",
        "upd_no_new": "✅ You have the latest version",
        "upd_err": "❌ Update Check Failed",
        "upd_downloading": "📥 Downloading update... {}%",
        "stat_total": "Total: {} | Done: {} | Errors: {}",
        "stat_size": "Size: {} / {}",
        "stat_eta": "Time left: {}",
        "tray_show": "Show/Hide",
        "tray_exit": "Exit",
        "ctx_folder": "📂 Open in Folder",
        "ctx_extract_icon": "🖼 Extract Icon",
        "ctx_rename_pkg": "✏ Rename PKG",
        "col_visibility": "Show/Hide Columns",
        "mini_mode": "Mini Mode",
        "logs_title": "📋 Logs",
        "logs_copy": "📋 Copy",
        "logs_clear": "🗑 Clear",
        "logs_close": "✖ Close",
        "logs_empty": "(No logs yet)",
        "logs_cleared": "(Logs cleared)",
        "ftp_pc": "PC:",
        "ftp_ps4": "PS4:",
        "ftp_connect": "🔗 Connect",
        "ftp_disconnect": "❌ Disconnect",
        "ftp_upload": "➡ Upload",
        "ftp_download": "⬅ Download",
        "ftp_mkdir": "📁 MkDir",
        "ftp_delete": "❌ Delete",
        "ftp_name": "Name",
        "ftp_size": "Size",
        "ftp_date": "Date",
        "ftp_refresh": "Refresh",
        "pkg_connect": "🔗 Connect",
        "pkg_refresh": "🔄 Refresh",
        "pkg_launch": "🚀 Launch",
        "pkg_uninstall": "🗑 Uninstall",
        "pkg_title": "Title",
        "pkg_tid": "Title ID",
        "pkg_ver": "Version",
        "pkg_size": "Size",
        "bp_title": "Backport Tool",
        "bp_my_list": "My List",
        "bp_all_fw": "All Firmwares",
        "bp_target": "Target: {}",
        "bp_fw": "Select Firmware:",
        "bp_save": "Save Folder:",
        "bp_start": "Start",
        "bp_browse": "Browse",
        "ctx_change_title": "✏ Change Display Title",
        "change_title": "Change Title",
        "new_title": "New Title:",
        "icon_preview": "Icon Preview",
        "ok": "OK",
        "cancel": "Cancel",
        "confirm_exit_text": "Exit program or minimize to tray?",
        "btn_exit": "Exit",
        "btn_tray": "Minimize to Tray",
        "ok": "OK",
        "cancel": "Cancel",
        "bp_pass_title": "Enter PKG Passcode",
        "bp_pass_info": "This Retail PKG is encrypted with a unique passcode.\nPlease enter the 32-character passcode:",
        "bp_pass_extract": "📂 Extract from Base PKG (Game)",
        "bp_pass_extract_tip": "Select the Base Game PKG (FPKG) to extract its passcode",
        "bp_my_list_settings": "Custom Backport List",
        "bp_pass_select_base": "Select Base Game PKG (FPKG)",
        "bp_pass_found": "✅ Passcode found!\n{}",
        "bp_pass_not_found_title": "Not Found",
        "bp_pass_not_found": "❌ Passcode not found in PKG info.\nMake sure it is an FPKG or Base Game.",
        "ftp_search_placeholder": "Search local...",
        "ftp_search_placeholder_remote": "Search remote...",
        "recursive": "Recursive",
        "concurrent_installs": "Concurrent Installs:",
        "scan_folder": "Scanning folder...",
        "add_files": "Adding {} files...",
        "scan_dropped_folders": "Scanning dropped folders...",
        "add_dropped_files": "Adding {} dropped files...",
        "ftp_searching": "🔎 Searching...",
        "concurrent_installs": "Concurrent Installs:"
    }
}

# --- STYLES & THEMES ---
ICON_BTN_STYLE = """
    QPushButton#iconBtn { background-color: rgba(128, 128, 128, 0.2); border: 1px solid #888; border-radius: 4px; }
    QPushButton#iconBtn:hover { background-color: rgba(128, 128, 128, 0.4); border-color: #aaa; }
"""
STD_INPUT = "padding: 4px;"
STD_HEADER = "padding: 4px; font-weight: bold;"
MODERN_BTN = "padding: 6px;"

SPINBOX_FIX = """
    QSpinBox::up-button, QSpinBox::down-button { width: 16px; background: #444; border: 1px solid #555; }
    QSpinBox::up-arrow { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #fff; }
    QSpinBox::down-arrow { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #fff; }
"""

THEMES = {
    "Dark (Default)": { "bg": "#121212", "fg": "#e0e0e0", "input_bg": "#252525", "input_fg": "white", "input_border": "#444", "btn_bg": "#2d2d2d", "btn_fg": "white", "tree_bg": "#1e1e1e", "tree_alt": "#242424", "header_bg": "#252525", "type": "dark" },
    "Polar White": { "bg": "#ffffff", "fg": "#333333", "input_bg": "#f7f7f7", "input_fg": "#333", "input_border": "#ccc", "btn_bg": "#f0f0f0", "btn_fg": "#333", "tree_bg": "#ffffff", "tree_alt": "#f9f9f9", "header_bg": "#f0f0f0", "type": "light" },
    "Dracula": { "bg": "#282a36", "fg": "#f8f8f2", "input_bg": "#44475a", "input_fg": "#f8f8f2", "input_border": "#6272a4", "btn_bg": "#44475a", "btn_fg": "#f8f8f2", "tree_bg": "#282a36", "tree_alt": "#2d303e", "header_bg": "#44475a", "type": "dark" },
    "Solarized Dark": { "bg": "#002b36", "fg": "#839496", "input_bg": "#073642", "input_fg": "#93a1a1", "input_border": "#586e75", "btn_bg": "#073642", "btn_fg": "#93a1a1", "tree_bg": "#002b36", "tree_alt": "#073642", "header_bg": "#073642", "type": "dark" },
    "Solarized Light": { "bg": "#fdf6e3", "fg": "#657b83", "input_bg": "#eee8d5", "input_fg": "#586e75", "input_border": "#93a1a1", "btn_bg": "#eee8d5", "btn_fg": "#586e75", "tree_bg": "#fdf6e3", "tree_alt": "#eee8d5", "header_bg": "#eee8d5", "type": "light" },
    "Monokai": { "bg": "#272822", "fg": "#f8f8f2", "input_bg": "#3e3d32", "input_fg": "#f8f8f2", "input_border": "#75715e", "btn_bg": "#3e3d32", "btn_fg": "#f8f8f2", "tree_bg": "#272822", "tree_alt": "#323329", "header_bg": "#3e3d32", "type": "dark" },
    "Nord": { "bg": "#2e3440", "fg": "#d8dee9", "input_bg": "#3b4252", "input_fg": "#e5e9f0", "input_border": "#4c566a", "btn_bg": "#3b4252", "btn_fg": "#e5e9f0", "tree_bg": "#2e3440", "tree_alt": "#3b4252", "header_bg": "#3b4252", "type": "dark" },
    "Cyberpunk": { "bg": "#0b0c15", "fg": "#00ff9f", "input_bg": "#1c1c2e", "input_fg": "#f0f0f0", "input_border": "#ff003c", "btn_bg": "#1c1c2e", "btn_fg": "#00ff9f", "tree_bg": "#0b0c15", "tree_alt": "#12121e", "header_bg": "#1c1c2e", "type": "dark" },
    "Matrix": { "bg": "#000000", "fg": "#00ff00", "input_bg": "#111111", "input_fg": "#00ff00", "input_border": "#004400", "btn_bg": "#0a0a0a", "btn_fg": "#00ff00", "tree_bg": "#000000", "tree_alt": "#0a0a0a", "header_bg": "#003300", "type": "dark" },
    "Deep Ocean": { "bg": "#0f172a", "fg": "#e2e8f0", "input_bg": "#1e293b", "input_fg": "#f1f5f9", "input_border": "#334155", "btn_bg": "#1e293b", "btn_fg": "#e2e8f0", "tree_bg": "#0f172a", "tree_alt": "#162035", "header_bg": "#1e293b", "type": "dark" },
    "Forest": { "bg": "#1a2f1c", "fg": "#e0f2e1", "input_bg": "#2d4a30", "input_fg": "#ffffff", "input_border": "#4caf50", "btn_bg": "#2d4a30", "btn_fg": "#e0f2e1", "tree_bg": "#1a2f1c", "tree_alt": "#223b24", "header_bg": "#2d4a30", "type": "dark" },
    "Midnight Blue": { "bg": "#000033", "fg": "#cccccc", "input_bg": "#000055", "input_fg": "#ffffff", "input_border": "#000077", "btn_bg": "#000055", "btn_fg": "#cccccc", "tree_bg": "#000033", "tree_alt": "#000044", "header_bg": "#000055", "type": "dark" },
    "Sunset": { "bg": "#2d1b2e", "fg": "#ffd1dc", "input_bg": "#4a2c4e", "input_fg": "#ffffff", "input_border": "#b56576", "btn_bg": "#4a2c4e", "btn_fg": "#ffd1dc", "tree_bg": "#2d1b2e", "tree_alt": "#3a223a", "header_bg": "#4a2c4e", "type": "dark" },
    "Grey": { "bg": "#333333", "fg": "#eeeeee", "input_bg": "#444444", "input_fg": "#ffffff", "input_border": "#555555", "btn_bg": "#444444", "btn_fg": "#eeeeee", "tree_bg": "#333333", "tree_alt": "#3a3a3a", "header_bg": "#444444", "type": "dark" },
    "Discord": { "bg": "#36393f", "fg": "#dcddde", "input_bg": "#40444b", "input_fg": "#ffffff", "input_border": "#202225", "btn_bg": "#40444b", "btn_fg": "#dcddde", "tree_bg": "#36393f", "tree_alt": "#2f3136", "header_bg": "#202225", "type": "dark" },
    "Ubuntu": { "bg": "#300a24", "fg": "#ffffff", "input_bg": "#471336", "input_fg": "#ffffff", "input_border": "#77216f", "btn_bg": "#5e2750", "btn_fg": "#ffffff", "tree_bg": "#300a24", "tree_alt": "#3b0c2c", "header_bg": "#471336", "type": "dark" },
    "Mint": { "bg": "#212121", "fg": "#00ffcc", "input_bg": "#333333", "input_fg": "#00ffcc", "input_border": "#009688", "btn_bg": "#333333", "btn_fg": "#00ffcc", "tree_bg": "#212121", "tree_alt": "#282828", "header_bg": "#333333", "type": "dark" },
    "Coffee": { "bg": "#2d241f", "fg": "#d6c3b6", "input_bg": "#42362e", "input_fg": "#f0e6dd", "input_border": "#6b5446", "btn_bg": "#42362e", "btn_fg": "#d6c3b6", "tree_bg": "#2d241f", "tree_alt": "#362b25", "header_bg": "#42362e", "type": "dark" },
    "Steel": { "bg": "#1c2329", "fg": "#b0c4de", "input_bg": "#2a343d", "input_fg": "#ffffff", "input_border": "#4682b4", "btn_bg": "#2a343d", "btn_fg": "#b0c4de", "tree_bg": "#1c2329", "tree_alt": "#222a30", "header_bg": "#2a343d", "type": "dark" },
    "High Contrast": { "bg": "#000000", "fg": "#ffffff", "input_bg": "#000000", "input_fg": "#ffffff", "input_border": "#ffffff", "btn_bg": "#000000", "btn_fg": "#ffffff", "tree_bg": "#000000", "tree_alt": "#111111", "header_bg": "#000000", "type": "dark" },
    "Hackerman": { "bg": "#0d0208", "fg": "#008f11", "input_bg": "#1a0410", "input_fg": "#00ff41", "input_border": "#003b00", "btn_bg": "#1a0410", "btn_fg": "#00ff41", "tree_bg": "#0d0208", "tree_alt": "#14030c", "header_bg": "#1a0410", "type": "dark" },
    "Red Velvet": { "bg": "#2b0000", "fg": "#ffdddd", "input_bg": "#450000", "input_fg": "#ffffff", "input_border": "#800000", "btn_bg": "#450000", "btn_fg": "#ffdddd", "tree_bg": "#2b0000", "tree_alt": "#350000", "header_bg": "#450000", "type": "dark" },
    "Purple Haze": { "bg": "#1a0b2e", "fg": "#e0b0ff", "input_bg": "#2d164f", "input_fg": "#ffffff", "input_border": "#663399", "btn_bg": "#2d164f", "btn_fg": "#e0b0ff", "tree_bg": "#1a0b2e", "tree_alt": "#240f3e", "header_bg": "#2d164f", "type": "dark" },
    "Gold": { "bg": "#1a1a10", "fg": "#ffd700", "input_bg": "#2b2b1a", "input_fg": "#ffeb3b", "input_border": "#b8860b", "btn_bg": "#2b2b1a", "btn_fg": "#ffd700", "tree_bg": "#1a1a10", "tree_alt": "#232316", "header_bg": "#2b2b1a", "type": "dark" },
    "Carbon": { "bg": "#181818", "fg": "#b0b0b0", "input_bg": "#252525", "input_fg": "#e0e0e0", "input_border": "#3a3a3a", "btn_bg": "#252525", "btn_fg": "#b0b0b0", "tree_bg": "#181818", "tree_alt": "#1f1f1f", "header_bg": "#252525", "type": "dark" },
    "Slate": { "bg": "#23272e", "fg": "#abb2bf", "input_bg": "#2c313a", "input_fg": "#ffffff", "input_border": "#5c6370", "btn_bg": "#2c313a", "btn_fg": "#abb2bf", "tree_bg": "#23272e", "tree_alt": "#292d35", "header_bg": "#2c313a", "type": "dark" },
    "Navy": { "bg": "#001f3f", "fg": "#7fdbff", "input_bg": "#003366", "input_fg": "#ffffff", "input_border": "#0074d9", "btn_bg": "#003366", "btn_fg": "#7fdbff", "tree_bg": "#001f3f", "tree_alt": "#002850", "header_bg": "#003366", "type": "dark" },
    "Pinky": { "bg": "#290015", "fg": "#ff99cc", "input_bg": "#420022", "input_fg": "#ffffff", "input_border": "#800040", "btn_bg": "#420022", "btn_fg": "#ff99cc", "tree_bg": "#290015", "tree_alt": "#33001a", "header_bg": "#420022", "type": "dark" },
    "Storm Blue": { "bg": "#151e24", "fg": "#d4e6f1", "input_bg": "#212f38", "input_fg": "#ffffff", "input_border": "#34495e", "btn_bg": "#212f38", "btn_fg": "#d4e6f1", "tree_bg": "#151e24", "tree_alt": "#1a252d", "header_bg": "#212f38", "type": "dark" },
    # --- ULTRA COLLECTION (NEW) ---
    "Neon City (Ultra)": { 
        "bg": "#050505", "fg": "#00f3ff", "input_bg": "#0a0a0a", "input_fg": "#ff0099", 
        "input_border": "#00f3ff", "btn_bg": "#111111", "btn_fg": "#00f3ff", 
        "tree_bg": "#050505", "tree_alt": "#0d0d0d", "header_bg": "#111111", "type": "dark" 
    },
    "Radioactive (Ultra)": { 
        "bg": "#0a0f00", "fg": "#ccff00", "input_bg": "#141f00", "input_fg": "#ffffff", 
        "input_border": "#66ff00", "btn_bg": "#1f3300", "btn_fg": "#ccff00", 
        "tree_bg": "#0a0f00", "tree_alt": "#0f1600", "header_bg": "#141f00", "type": "dark" 
    },
    "Vaporwave 80s (Ultra)": { 
        "bg": "#240046", "fg": "#ff9e00", "input_bg": "#3c096c", "input_fg": "#ff9e00", 
        "input_border": "#9d4edd", "btn_bg": "#5a189a", "btn_fg": "#e0aaff", 
        "tree_bg": "#240046", "tree_alt": "#2d0055", "header_bg": "#3c096c", "type": "dark" 
    },
    "Obsidian Glass (Ultra)": { 
        "bg": "#000000", "fg": "#e0e0e0", "input_bg": "#1a1a1a", "input_fg": "#ffffff", 
        "input_border": "#333333", "btn_bg": "#1a1a1a", "btn_fg": "#ffffff", 
        "tree_bg": "#000000", "tree_alt": "#0d0d0d", "header_bg": "#1a1a1a", "type": "dark" 
    },
    "Crimson Fury (Ultra)": { 
        "bg": "#1a0000", "fg": "#ff4d4d", "input_bg": "#330000", "input_fg": "#ffffff", 
        "input_border": "#ff0000", "btn_bg": "#4d0000", "btn_fg": "#ffcccc", 
        "tree_bg": "#1a0000", "tree_alt": "#260000", "header_bg": "#330000", "type": "dark" 
    },
    "Deep Space (Ultra)": { 
        "bg": "#020c1b", "fg": "#64ffda", "input_bg": "#112240", "input_fg": "#e6f1ff", 
        "input_border": "#233554", "btn_bg": "#0a192f", "btn_fg": "#64ffda", 
        "tree_bg": "#020c1b", "tree_alt": "#061223", "header_bg": "#112240", "type": "dark" 
    },
    "Golden Luxury (Ultra)": { 
        "bg": "#121212", "fg": "#ffd700", "input_bg": "#1c1c1c", "input_fg": "#ffffff", 
        "input_border": "#cfb53b", "btn_bg": "#262626", "btn_fg": "#ffd700", 
        "tree_bg": "#121212", "tree_alt": "#1a1a1a", "header_bg": "#1c1c1c", "type": "dark" 
    },
    "Hacker Green (Ultra)": { 
        "bg": "#000000", "fg": "#00ff00", "input_bg": "#001100", "input_fg": "#00ff00", 
        "input_border": "#003300", "btn_bg": "#002200", "btn_fg": "#00ff00", 
        "tree_bg": "#000000", "tree_alt": "#000d00", "header_bg": "#001100", "type": "dark" 
    },
    "Oceanic Zen (Ultra)": { 
        "bg": "#001e26", "fg": "#00d4ff", "input_bg": "#003542", "input_fg": "#ffffff", 
        "input_border": "#005f73", "btn_bg": "#0a9396", "btn_fg": "#ffffff", 
        "tree_bg": "#001e26", "tree_alt": "#002933", "header_bg": "#003542", "type": "dark" 
    },
    "Ghost White (Ultra)": { 
        "bg": "#f0f2f5", "fg": "#1c1e21", "input_bg": "#ffffff", "input_fg": "#000000", 
        "input_border": "#1877f2", "btn_bg": "#e4e6eb", "btn_fg": "#050505", 
        "tree_bg": "#ffffff", "tree_alt": "#f7f8fa", "header_bg": "#ffffff", "type": "light" 
    }
}

# --- UTILS ---
class SpeedCalculator:
    def __init__(self, smoothing_window=20):  # Increased from 10 to 20 for smoother speed display
        self.history = deque(maxlen=smoothing_window)
        self.last_time = time.time()
        self.last_bytes = 0

    def reset(self):
        self.history.clear()
        self.last_time = time.time()
        self.last_bytes = 0

    def update(self, current_bytes, force=False):
        now = time.time()
        dt = now - self.last_time
        if not force and dt < 0.2: return None 
        diff = current_bytes - self.last_bytes
        if diff < 0: diff = 0 
        if dt <= 0: dt = 0.000001 # Prevent ZeroDivision for instant transfers
        speed = diff / dt
        self.history.append(speed)
        self.last_time = now
        self.last_bytes = current_bytes
        avg_speed = sum(self.history) / len(self.history) if self.history else 0
        return avg_speed

class SFOEditor:
    def __init__(self, data=None, file_path=None):
        self.entries = [] # List of dicts: {key, fmt, len, max_len, data}
        self.file_path = file_path
        if data: self.parse(data)
        elif file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f: self.parse(f.read())
            
    def parse(self, data):
        try:
            if data[:4] != b'\x00PSF': return
            key_table_start = struct.unpack_from('<I', data, 0x08)[0]
            data_table_start = struct.unpack_from('<I', data, 0x0C)[0]
            entries_count = struct.unpack_from('<I', data, 0x10)[0]
            
            for i in range(entries_count):
                offset = 0x14 + (i * 16)
                key_off = struct.unpack_from('<H', data, offset)[0]
                fmt = struct.unpack_from('<H', data, offset + 2)[0]
                d_len = struct.unpack_from('<I', data, offset + 4)[0]
                max_len = struct.unpack_from('<I', data, offset + 8)[0]
                data_off = struct.unpack_from('<I', data, offset + 12)[0]
                
                # Read Key
                k_ptr = key_table_start + key_off
                k_end = data.find(b'\x00', k_ptr)
                if k_end == -1: k_end = len(data)
                key = data[k_ptr:k_end].decode('utf-8', errors='ignore')
                
                # Read Value
                v_ptr = data_table_start + data_off
                raw_val = data[v_ptr : v_ptr + max_len] # Read up to max_len
                
                # Integers are usually fmt 0x0404, Strings 0x0204 or 0x0004
                val = raw_val
                if fmt == 0x0404: # Integer
                     val = struct.unpack('<I', raw_val[:4])[0]
                elif fmt in [0x0204, 0x0004]: # String
                     val = raw_val.split(b'\x00')[0].decode('utf-8', errors='ignore')
                
                self.entries.append({
                    "key": key, "fmt": fmt, "len": d_len, "max_len": max_len, "value": val
                })
        except Exception as e: log(f"SFO Parse Error: {e}", "ERROR")

    def get(self, key, default=""):
        for e in self.entries:
            if e["key"] == key: return e["value"]
        return default
        
    def set_text(self, key, new_text):
        for e in self.entries:
            if e["key"] == key:
                # Truncate if strict? usually max_len includes null
                # We enforce max_len limit if > 0
                e["value"] = new_text
                # Update len? Rebuild will handle it
                return True
        return False

    def set_int(self, key, new_int):
        for e in self.entries:
             if e["key"] == key:
                 e["value"] = int(new_int)
                 return True
        return False
        
    def save(self, out_path=None):
        # Rebuild SFO
        if not out_path: out_path = self.file_path
        if not out_path: return False
        
        try:
             # Sort entries by key (SFO requirement usually? No, but cleaner)
             # Actually key_table needs implicit ordering if we construct strictly? 
             # Let's keep original order to be safe.
             
             # Build separate buffers
             index_table = bytearray()
             key_table = bytearray()
             data_table = bytearray()
             
             for e in self.entries:
                 k_offset = len(key_table)
                 d_offset = len(data_table)
                 
                 # Append Key
                 k_bytes = e["key"].encode('utf-8') + b'\x00'
                 key_table.extend(k_bytes)
                 
                 # Append Data
                 if e["fmt"] == 0x0404:
                     d_bytes = struct.pack('<I', e["value"])
                     # Padding usually matches max_len? 
                     needed = e["max_len"] - 4
                     if needed > 0: d_bytes += b'\x00' * needed
                     actual_len = 4
                 else:
                     enc = str(e["value"]).encode('utf-8')
                     # Ensure null term if string
                     actual_len = len(enc) + 1 # +1 for null
                     d_bytes = enc + b'\x00'
                     
                     # Check max_len constraint
                     if len(d_bytes) > e["max_len"]:
                         # Resize max_len if we are allowed?
                         # Usually safer to truncate or expand. 
                         # Let's EXPAND max_len if needed (most tools allow it)
                         # OR update e["max_len"] to match new content + buffer
                         padding = (4 - (len(d_bytes) % 4)) % 4 # 4-byte align?
                         # SFO strings usually fixed buffer. 
                         # Let's trust the user input and update max_len if we exceed it.
                         if len(d_bytes) > e["max_len"]: e["max_len"] = len(d_bytes) + (4 - (len(d_bytes)%4))
                     
                     # Padding to max_len
                     needed = e["max_len"] - len(d_bytes)
                     if needed > 0: d_bytes += b'\x00' * needed
                 
                 data_table.extend(d_bytes)
                 
                 # Entry: KeyOff(2), Fmt(2), Len(4), MaxLen(4), DataOff(4)
                 index_table.extend(struct.pack('<H', k_offset))
                 index_table.extend(struct.pack('<H', e["fmt"]))
                 index_table.extend(struct.pack('<I', actual_len))
                 index_table.extend(struct.pack('<I', e["max_len"]))
                 index_table.extend(struct.pack('<I', d_offset))
             
             # Calculate Header Offsets
             header_size = 0x14
             entries_count = len(self.entries)
             # Index Table follows header. Size = 16 * count
             index_size = entries_count * 16
             
             key_table_start = header_size + index_size
             data_table_start = key_table_start + len(key_table)
             
             # align data table start?
             # data_table_start often 4-byte aligned. key_table usually ends cleanly?
             
             header = bytearray(b'\x00PSF')
             header.extend(struct.pack('<I', 0x0101)) # version
             header.extend(struct.pack('<I', key_table_start))
             header.extend(struct.pack('<I', data_table_start))
             header.extend(struct.pack('<I', entries_count))
             
             final_data = header + index_table + key_table + data_table
             
             with open(out_path, "wb") as f: f.write(final_data)
             return True
        except Exception as e:
            log(f"SFO Save Error: {e}", "ERROR")
            return False

def get_pkg_info_from_sfo(sfo_data):
    parser = SFOEditor(data=sfo_data)
    return {
        "TITLE": parser.get("TITLE") or parser.get("Title"), 
        "TITLE_ID": parser.get("TITLE_ID") or parser.get("Title_ID"), 
        "APP_VER": parser.get("APP_VER") or parser.get("App_Ver"),
        "CATEGORY": parser.get("CATEGORY") or parser.get("Category")
    }



class GridDelegate(QStyledItemDelegate):
    def __init__(self, color_hex="#3a3a3a", height=30, parent=None):
        super().__init__(parent)
        self.color = QColor(color_hex); self.row_height = height 
    def sizeHint(self, option, index):
        s = super().sizeHint(option, index); s.setHeight(self.row_height); return s
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        painter.save(); painter.setPen(QPen(self.color, 1))
        bottom_start = option.rect.bottomLeft()
        if index.column() == 0: bottom_start.setX(0)
        painter.drawLine(bottom_start, option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.restore()

class CenterDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter; super().paint(painter, option, index)

class FTPItem(QTreeWidgetItem):
    def __init__(self, data):
        super().__init__(data)

    def __lt__(self, other):
        tw = self.treeWidget()
        if not tw: return super().__lt__(other)
        column = tw.sortColumn()
        order = tw.header().sortIndicatorOrder()
        is_asc = (order == Qt.SortOrder.AscendingOrder)
        
        # 1. Handle ".." (Parent directory) - ALWAYS at the top
        if self.text(0) == "..": return is_asc
        if other.text(0) == "..": return not is_asc
        
        # 2. Extract Data Roles (dir vs file)
        is_dir_self = self.data(0, Qt.ItemDataRole.UserRole) in ["dir", "UP"]
        is_dir_other = other.data(0, Qt.ItemDataRole.UserRole) in ["dir", "UP"]
        
        # 3. Folders first (if one is dir and other is not)
        if is_dir_self != is_dir_other:
            return is_dir_self if is_asc else not is_dir_self
            
        # 4. Standard sorting for other columns (Size, Date, etc.)
        if column == 1: # Size
            def get_size(txt):
                if not txt: return 0
                try:
                    parts = txt.split()
                    val = float(parts[0])
                    if "MB" in txt: val *= 1024*1024
                    elif "KB" in txt: val *= 1024
                    elif "GB" in txt: val *= 1024*1024*1024
                    return val
                except: return 0
            return get_size(self.text(1)) < get_size(other.text(1))
            
        # Default: Alphabetical (Case-insensitive)
        return self.text(column).lower() < other.text(column).lower()

FILE_STATES = {}
STATE_MUTEX = QMutex()
def set_file_state(key, state):
    STATE_MUTEX.lock(); FILE_STATES[key] = state; STATE_MUTEX.unlock()
def get_file_state(key):
    STATE_MUTEX.lock(); val = FILE_STATES.get(key, "IDLE"); STATE_MUTEX.unlock()
    return val

class ServerSignals(QObject):
    progress = pyqtSignal(str, int)
    status_msg = pyqtSignal(str)
    install_status = pyqtSignal(str, str, str)
    speed_update = pyqtSignal(str, float) 
    loader_root_created = pyqtSignal(str, str, int, bool, str)
    loader_file_found = pyqtSignal(str, str, str, str, str, str, "qint64", str)
    loader_batch_found = pyqtSignal(list) # List of file tuples
    loader_finished = pyqtSignal()
    scan_finished = pyqtSignal(list)
    backup_log = pyqtSignal(str); backup_started = pyqtSignal(); backup_finished = pyqtSignal()
    restore_log = pyqtSignal(str); restore_finished = pyqtSignal()
    username_found = pyqtSignal(str, str) 
    app_found = pyqtSignal(str, str, str, str)
    apps_scan_finished = pyqtSignal(list) 
    silent_scan_finished = pyqtSignal(dict) 
    update_found = pyqtSignal(str, str); update_not_found = pyqtSignal(); update_progress = pyqtSignal(int); update_finished = pyqtSignal(str)
    ping_result = pyqtSignal(dict)
    ftp_progress = pyqtSignal(int)
    show_image_preview = pyqtSignal(bytes, str) # FIX: Signal for thread-safe image preview
    
    # FIX: Signal / Variable for passcode request from BG thread
    request_passcode = pyqtSignal(str)
    passcode_result = None # To store result from GUI thread
    passcode_event = threading.Event() # To wait for GUI thread
    ftp_connected = pyqtSignal(bool)

server_signals = ServerSignals()

# --- STABLE SERVER ENGINE ---
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    
    def server_bind(self):
        # Опции для быстрого освобождения порта
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Попытка установить SO_REUSEPORT (не на всех ОС)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        try:
            # Revert to defaults -> let OS manage windows
            # Fast close is okay
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        except: pass
        HTTPServer.server_bind(self)

    # Suppress noisy socket errors on client disconnect
    def handle_error(self, request, client_address):
        try:
            _, val, _ = sys.exc_info()
            if isinstance(val, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
                # Expected behavior when client (PS4) cancels or disconnects
                return
            # On Windows, sometimes get socket.error with specific errno
            if hasattr(val, 'errno') and val.errno in (10053, 10054, 32):
                 return
        except: pass
        # Call default for other real errors
        super().handle_error(request, client_address)

class PS4HTTPHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    map_files = {}
    file_key_map = {} # Mapping: SanitizedName -> HashKey for progress tracking
    speed_calcs = {} 

    def _get_file_path(self, path):
        key = path.lstrip('/').split('?')[0]
        if key in self.map_files: return self.map_files[key]
        if key.endswith('.pkg'):
            k2 = key[:-4]
            if k2 in self.map_files: return self.map_files[k2]
        decoded = urllib.parse.unquote(key)
        if decoded in self.map_files: return self.map_files[decoded]
        if decoded.endswith('.pkg') and decoded[:-4] in self.map_files: return self.map_files[decoded[:-4]]
        return None
        
    def log_message(self, format, *args):
        # Suppress standard HTTP logs for 200/206 to avoid spam
        msg = format % args
        if '" 206 ' in msg or '" 200 ' in msg: return
        log(f"HTTP: {msg}", "HTTP")

    def do_HEAD(self):
        log(f"HEAD: {self.path}", "HTTP")
        try:
            fpath = self._get_file_path(self.path)
            if not fpath or not os.path.exists(fpath): 
                log(f"HEAD 404: {self.path}", "ERROR")
                self.send_error(404)
                return
            
            file_size = os.path.getsize(fpath)
            log(f"HEAD 200: {self.path} (Size: {file_size})", "DEBUG")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()
        except Exception as e:
            log(f"HEAD Error: {e}", "ERROR")

    def do_GET(self):
        # DEBUG: Log all GET requests to diagnose progress issues
        log(f"GET: {self.path}", "HTTP") 
        try:
            fpath = self._get_file_path(self.path)
            if not fpath or not os.path.exists(fpath): 
                log(f"GET 404: {self.path}", "ERROR")
                self.send_error(404)
                return
            
            key = self.path.lstrip('/').split('?')[0]
            decoded = urllib.parse.unquote(key)
            
            file_key = None
            
            # 1. Exact match
            if key in self.map_files: file_key = key
            elif decoded in self.map_files: file_key = decoded
            
            # 2. Try removing extension
            elif key.endswith('.pkg') and key[:-4] in self.map_files: file_key = key[:-4]
            elif decoded.endswith('.pkg') and decoded[:-4] in self.map_files: file_key = decoded[:-4]
            
            # FIX: If file_key is found (meaning it's a valid file), check if we have a mapped Hash Key for it.
            # This handles the case where URL is "Name.pkg" but UI ID is "12345".
            if file_key and file_key in self.file_key_map:
                file_key = self.file_key_map[file_key]
            
            # 3. Fallback: Lookup by VALUE (Slow, but safe for aliases)
            # if not file_key:
            #    for k, v in self.map_files.items():
            #        if v == fpath and k.isdigit(): # Assume digit keys are the 'real' IDs
            #             file_key = k; break
            
            # DEBUG: Log file_key resolution
            # log(f"GET file_key={file_key} from path={key}", "DEBUG")
            if not file_key:
                 log(f"WARNING: File key not found for {key}. Map keys example: {list(self.map_files.keys())[:3]}", "WARN")
            
            file_size = os.path.getsize(fpath)
            start, end = 0, file_size - 1
            status_code = 200
            
            range_header = self.headers.get('Range')
            if range_header:
                # Removed verbose range logging to reduce spam
                # log(f"GET Range Request: {range_header} for {self.path}", "DEBUG")
                try:
                    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
                    if m:
                        start = int(m.group(1))
                        if m.group(2): end = min(int(m.group(2)), file_size - 1)
                        if start >= file_size: 
                            log(f"GET 416 Range Not Satisfiable: {range_header}", "WARN")
                            self.send_error(416)
                            self.end_headers()
                            return
                        status_code = 206
                    else:
                        log(f"Failed to parse Range: {range_header}", "WARN")
                except Exception as e:
                    log(f"Range parse exception: {e}", "ERROR")
            else:
                if file_size < 1024*1024*10: # Only log full downloads for small files
                    log(f"GET Full File: {self.path} ({file_size} bytes)", "DEBUG")
            
            chunk_len = end - start + 1
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Accept-Ranges', 'bytes')
            if status_code == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.send_header('Content-Length', str(chunk_len))
            
            # FIX: Content-Disposition to help SPPI identify file type
            # Use original filename from path, or the requested key if it looks like a file
            real_filename = os.path.basename(fpath)
            safe_filename = urllib.parse.quote(real_filename)
            self.send_header('Content-Disposition', f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}')
            
            self.end_headers()
            
            # ... (send logic remains) ...
            
            if file_key:
                if file_key not in self.speed_calcs: 
                    self.speed_calcs[file_key] = SpeedCalculator()
                # FIX: Do NOT reset speed calculator on each range request - this causes speed jumps

            # FIX: Initialize variables BEFORE the with block to avoid UnboundLocalError
            bytes_sent = 0
            last_emit_pct = -1
            last_emit_time = 0
            last_speed_emit_time = 0
            checks_counter = 0

            with open(fpath, 'rb') as f:
                f.seek(start)
                
                while bytes_sent < chunk_len:
                    checks_counter += 1
                    if checks_counter >= 32: # Check every ~2MB (if 64KB chunks)
                        checks_counter = 0
                        if file_key:
                            state = get_file_state(file_key)
                            if state == "CANCELLED": return
                            while state == "PAUSED":
                                time.sleep(0.5)
                                state = get_file_state(file_key)
                                if state == "CANCELLED": return
                    
                    # STABILITY TUNING:
                    # 1MB chunks caused 10053 disconnects on some systems (buffer overflow/latency).
                    # 128KB-256KB is the sweet spot for Windows socket speeds without blocking kernel.
                    
                    is_tiny_file = (file_size < 1024 * 1024) # < 1MB
                    
                    if is_tiny_file:
                        # Only throttle extremely small files to avoid PS4 connection spam
                        read_size = min(32768, chunk_len - bytes_sent)
                        time.sleep(0.001) # Micro sleep
                    else:
                        # 256KB chunks = Balance between CPU calls and Network Throughput
                        read_size = min(262144, chunk_len - bytes_sent) 
                        # Micro-yield every 2MB to keep system responsive during heavy concurrent load
                        if checks_counter % 8 == 0:
                             time.sleep(0.001)
                    
                    chunk = f.read(read_size)
                    if not chunk: break
                    
                    try: self.wfile.write(chunk)
                    except Exception as e: 
                        # Suppress common "connection reset" error (PS4 closing connection)
                        err_str = str(e)
                        if "10054" in err_str or "10053" in err_str or "32" in err_str:
                            log(f"Connection closed by client (normal)", "DEBUG")
                        else:
                            log(f"Write error (client disconnect): {e}", "WARN")
                        return
                    
                    bytes_sent += len(chunk)
                    
                    if file_key:
                        is_finished = (bytes_sent >= chunk_len)
                        # FIX: Use absolute position (start + bytes_sent) for consistent speed tracking across chunks
                        avg_spd = self.speed_calcs[file_key].update(start + bytes_sent, force=is_finished)
                        
                        t = time.time()
                        if avg_spd is not None:
                             # THRESHOLD: Only emit speed updates every 1.0s or at completion
                             if t - last_speed_emit_time > 1.0 or is_finished:
                                  server_signals.speed_update.emit(file_key, avg_spd)
                                  last_speed_emit_time = t

                        pct = int((start + bytes_sent) * 100 / file_size)
                        # Update progress less frequently (0.5s) to avoid spamming signals during multi-installs
                        if pct > last_emit_pct and (t - last_emit_time > 0.5 or pct == 100):
                            server_signals.progress.emit(file_key, pct)
                            last_emit_pct = pct
                            last_emit_time = t
        except Exception as e:
            log(f"do_GET error: {e}", "ERROR")

# --- HELPER FUNCTIONS ---

def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = 0
    p = float(size_bytes)
    while p >= 1024.0 and i < len(size_name) - 1:
        p /= 1024.0
        i += 1
    return f"{p:.2f} {size_name[i]}".replace('.', ',')

def parse_pkg_info(filepath):
    tid, ver, region, category = "Unknown", "01.00", "-", "-"
    if filepath.lower().endswith(".bin"):
        return "PAYLOAD", "-", "-", "PAYLOAD"
        
    try:
        filename_lower = os.path.basename(filepath).lower()
        
        with open(filepath, 'rb') as f:
            # Read first 32MB to find SFO and other data
            data = f.read(32 * 1024 * 1024) 
            
            # 1. Detect Category from filename/binary as FALLBACK
            if '_dlc_' in filename_lower or 'dlc' in filename_lower or 'addcont' in filename_lower or 'season' in filename_lower:
                category = "DLC"
            elif '_patch_' in filename_lower or 'patch' in filename_lower or 'update' in filename_lower or 'backport' in filename_lower or 'fix' in filename_lower:
                category = "UPDATE"
            elif b'ac.pkg' in data[:0x1000] or b'addcont' in data[:0x5000]:
                category = "DLC"
            elif b'patch' in data[:0x5000]:
                category = "UPDATE"
            
            # 2. Extract Region from Content ID
            m_cid = re.search(rb'([UEJAHIK][PSCN]\d{4})-([A-Z]{4}\d{5})_00', data)
            if m_cid:
                region_code = m_cid.group(1).decode('ascii')[:2]
                region_map = {'UP': 'US', 'EP': 'EU', 'JP': 'JP', 'HP': 'HK', 'AS': 'AS', 'KP': 'KR'}
                region = region_map.get(region_code, region_code)

            # 3. SFO Ground Truth (Highest Priority)
            offset = 0
            while True:
                sfo_offset = data.find(b'\x00PSF', offset)
                if sfo_offset == -1: break
                try:
                    sfo_data = data[sfo_offset : sfo_offset + 5000] 
                    sfo_info = get_pkg_info_from_sfo(sfo_data)
                    found_tid = sfo_info.get("TITLE_ID")
                    found_ver = sfo_info.get("APP_VER")
                    sfo_cat = sfo_info.get("CATEGORY")
                    
                    if found_tid: tid = found_tid.strip().upper()
                    if found_ver: ver = found_ver
                    
                    if sfo_cat:
                        s_cat = sfo_cat.lower()
                        if s_cat == "gd": category = "GAME"
                        elif s_cat == "gp": category = "UPDATE"
                        elif s_cat == "ac": category = "DLC"
                        elif s_cat == "sd": category = "THEME"
                except: pass
                offset = sfo_offset + 4 

            # Final Regex Fallback for TID if SFO failed
            if tid == "Unknown":
                m_tid = re.search(rb'(CUSA\d{5}|PPSA\d{5})', data)
                if m_tid: tid = m_tid.group(1).decode('ascii').upper()
            
            if category == "-" and (tid.startswith('CUSA') or tid.startswith('PPSA')):
                category = "GAME"
            elif category == "-":
                category = "APP"

    except Exception as e: 
        print(f"Error parsing {filepath}: {e}")
    return tid, ver, region, category
# --- THREAD CLASSES ---

class ScanThread(QThread):
    def run(self):
        valid_ips = []
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith(("127.", "169.254", "25.")):
                        base = ".".join(addr.address.split(".")[:-1]) + "."
                        valid_ips.extend([base + str(i) for i in range(1, 255)])
        except: pass
        
        def check(ip):
            # STRICT SCAN MODE: Only look for GolHEN FTP (2121) with banner verification.
            # This is the only 100% reliable way to filter out non-PS4 devices.
            
            s_ftp = None
            try:
                s_ftp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s_ftp.settimeout(0.5)
                s_ftp.connect((ip, 2121))
                banner = s_ftp.recv(1024)
                # Strict check: Banner must contain specific PS4/GoldHEN identifiers
                if b"220" in banner and (b"GoldHEN" in banner or b"PS4" in banner or b"Orbis" in banner):
                    return ip, 2121
            except: pass
            finally:
                if s_ftp: 
                    try: s_ftp.close()
                    except: pass

            # Note: 12800 (RPI) and 12813 (SPPI) are purposely omitted from Discovery.
            # If you need them, add "PS4 IP" manually. This keeps the scan list clean.
            return None
            
        found_results = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            for res in ex.map(check, list(set(valid_ips))):
                if res: found_results.append(res)
        server_signals.scan_finished.emit(found_results)

class SilentAppsScanner(QThread):
    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        self.port = 2121
    def run(self):
        installed_db = {}
        try:
            ftp = ftplib.FTP()
            ftp.connect(self.ip, self.port, timeout=5)
            ftp.login()
            ftp.voidcmd('TYPE I')
            try:
                ftp.cwd("/user/app/")
                cusas = ftp.nlst()
            except:
                server_signals.silent_scan_finished.emit({})
                return
            
            for cusa in cusas:
                if not cusa.startswith("CUSA") and not cusa.startswith("PPSA"): continue
                ver = "00.00"
                sfo_paths = [f"/user/app/{cusa}/sce_sys/param.sfo", f"/user/appmeta/{cusa}/param.sfo"]
                for path in sfo_paths:
                    try:
                        buf = io.BytesIO()
                        ftp.retrbinary(f"RETR {path}", buf.write)
                        data = buf.getvalue()
                        if len(data) > 0:
                            info = get_pkg_info_from_sfo(data)
                            if info["APP_VER"]: 
                                ver = info["APP_VER"]
                                break
                    except: continue
                installed_db[cusa] = ver
            ftp.quit()
        except: pass
        server_signals.silent_scan_finished.emit(installed_db)

class UpdateCheckerThread(QThread):
    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "").replace("v", "")
                def parse_ver(v): return [int(x) for x in v.split('.') if x.isdigit()]
                
                try:
                    remote = parse_ver(tag)
                    local = parse_ver(CURRENT_VERSION.split('-')[0])
                    if remote > local:
                        assets = data.get("assets", [])
                        exe_url = ""
                        for asset in assets:
                            if asset["name"].endswith(".exe"):
                                exe_url = asset["browser_download_url"]
                                break
                        if not exe_url and assets: exe_url = data["html_url"]
                        if exe_url:
                            server_signals.update_found.emit(tag, exe_url)
                            return
                except: pass
            server_signals.update_not_found.emit()
        except: server_signals.update_not_found.emit()

class UpdateDownloaderThread(QThread):
    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path
    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(self.dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            prog = int((downloaded / total_size) * 100)
                            server_signals.update_progress.emit(prog)
            server_signals.update_finished.emit(self.dest_path)
        except: server_signals.update_finished.emit("")

class LoaderThread(QThread):
    def __init__(self, data, is_startup=False, theme_type="dark", mode="folder", batch_size=50):
        super().__init__()
        self.data = data
        self.is_startup = is_startup
        self.theme_type = theme_type
        self.mode = mode
        self.batch_size = batch_size
        self.batch_buffer = []

    def flush_batch(self):
        if self.batch_buffer:
            server_signals.loader_batch_found.emit(self.batch_buffer)
            self.batch_buffer = []
            
    def add_to_batch(self, item):
        self.batch_buffer.append(item)
        if len(self.batch_buffer) >= self.batch_size:
            self.flush_batch()
            time.sleep(0.01) # Small yield to let GUI process batch

    def run(self):
        self.batch_buffer = []
        if self.mode == "folder":
            for folder_path in self.data:
                if os.path.exists(folder_path):
                    server_signals.loader_root_created.emit(folder_path, os.path.basename(folder_path), 0, self.is_startup, self.theme_type)
                    self.scan_recursive(folder_path, folder_path, 0)
            self.flush_batch()
            
        elif self.mode == "files":
            # Collect file info for sorting
            file_data = []
            for file_path in self.data:
                if os.path.exists(file_path) and file_path.lower().endswith((".pkg", ".bin")):
                    try:
                        f_size = os.path.getsize(file_path)
                        tid, ver, region, category = parse_pkg_info(file_path)
                        file_data.append((file_path, tid, ver, region, category, f_size))
                    except: pass
            
            # Sort by category: GAME -> UPDATE -> DLC -> Other
            def category_sort_key(item):
                cat = (item[4] or "").upper()
                if cat in ("GD", "GAME"):
                    return (0, os.path.basename(item[0]).lower())
                elif cat in ("GP", "UPDATE", "PATCH"):
                    return (1, os.path.basename(item[0]).lower())
                elif cat in ("AC", "DLC", "ADDON"):
                    return (2, os.path.basename(item[0]).lower())
                else:
                    return (3, os.path.basename(item[0]).lower())
            
            file_data.sort(key=category_sort_key)
            
            # Batch Emit sorted files
            for file_path, tid, ver, region, category, f_size in file_data:
                # Format matches signal: parent_path, name, tid, ver, region, category, size, full_path
                item = ("ROOT_MISC", os.path.basename(file_path), tid, ver, region, category, f_size, file_path)
                self.add_to_batch(item)
            self.flush_batch()
        
        server_signals.loader_finished.emit()

    def scan_recursive(self, path, root_path, depth):
        try:
            # time.sleep(0.001) # Removed in favor of batch yield
            entries = list(os.scandir(path))
            
            # Separate directories and files
            dirs = sorted([e for e in entries if e.is_dir()], key=lambda x: x.name.lower())
            files = [e for e in entries if e.is_file() and e.name.lower().endswith((".pkg", ".bin"))]
            
            # Process directories first
            for e in dirs:
                server_signals.loader_root_created.emit(e.path, e.name, depth + 1, self.is_startup, self.theme_type)
                self.scan_recursive(e.path, root_path, depth + 1)
            
            # Collect file info for sorting
            file_data = []
            for e in files:
                try:
                    f_size = e.stat().st_size
                    tid, ver, region, category = parse_pkg_info(e.path)
                    file_data.append((e, tid, ver, region, category, f_size))
                except:
                    pass
            
            # Sort by category: GAME (gd) -> UPDATE (gp) -> DLC (ac) -> Other
            def category_sort_key(item):
                cat = (item[4] or "").upper()
                if cat in ("GD", "GAME"):
                    return (0, item[0].name.lower())
                elif cat in ("GP", "UPDATE", "PATCH"):
                    return (1, item[0].name.lower())
                elif cat in ("AC", "DLC", "ADDON"):
                    return (2, item[0].name.lower())
                else:
                    return (3, item[0].name.lower())
            
            file_data.sort(key=category_sort_key)
            
            # Batch Emit sorted files
            for e, tid, ver, region, category, f_size in file_data:
                # Format matches signal: parent_path, name, tid, ver, region, category, size, full_path
                item = (path, e.name, tid, ver, region, category, f_size, e.path)
                self.add_to_batch(item)
                
        except: pass

class BackupThread(QThread):
    def __init__(self, ip, port, local_path, interval, enabled):
        super().__init__()
        self.ip = ip; self.port = 2121; self.local_root = local_path; self.interval = interval; self.enabled = enabled
        self.running = True; self.last_backup_time = 0; self.initial_backup_done = False; self.force_run = False
    def update_settings(self, ip, local_path, interval, enabled):
        self.ip = ip; self.local_root = local_path; self.interval = interval; self.enabled = enabled
        if not enabled: self.initial_backup_done = False
    def trigger_backup(self): self.force_run = True
    def run(self):
        while self.running:
            conn_ok = False
            if self.enabled and self.ip and self.local_root:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1)
                        if s.connect_ex((self.ip, self.port)) == 0: conn_ok = True
                except: pass
            
            should_run = False
            if self.force_run:
                if conn_ok: server_signals.backup_log.emit("🚀 Ручной запуск бэкапа..."); should_run = True
                else: server_signals.backup_log.emit("❌ Ошибка: FTP (2121) недоступен."); self.force_run = False
            elif conn_ok and self.enabled:
                now = time.time()
                if not self.initial_backup_done: server_signals.backup_log.emit("🔍 PS4 обнаружена. Начат бэкап..."); should_run = True
                elif (now - self.last_backup_time) > (self.interval * 60): server_signals.backup_log.emit(f"⏰ Интервал прошел. Бэкап..."); should_run = True
            
            if should_run and conn_ok:
                self.do_ftp_backup()
                self.last_backup_time = time.time(); self.initial_backup_done = True; self.force_run = False
            
            for _ in range(20): 
                if not self.running: break
                time.sleep(0.1)

    def do_ftp_backup(self):
        server_signals.backup_started.emit()
        try:
            ftp = ftplib.FTP(); ftp.connect(self.ip, self.port, timeout=10); ftp.login()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_folder = os.path.join(self.local_root, f"Backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)
            
            ftp.cwd("/user/home/")
            users = ftp.nlst()
            for user in users:
                if user in [".", ".."]: continue
                save_path = f"/user/home/{user}/savedata"
                try:
                    ftp.cwd(save_path)
                    local_user_path = os.path.join(backup_folder, "user", "home", user, "savedata")
                    os.makedirs(local_user_path, exist_ok=True)
                    self._mirror_ftp_dir(ftp, save_path, local_user_path)
                    ftp.cwd("/user/home/") 
                except: ftp.cwd("/user/home/"); continue
            ftp.quit()
            server_signals.backup_log.emit(f"✅ Бэкап завершен.")
        except Exception as e: server_signals.backup_log.emit(f"❌ Ошибка бэкапа: {str(e)}")
        finally: server_signals.backup_finished.emit()

    def _mirror_ftp_dir(self, ftp, remote_dir, local_dir):
        try:
            ftp.cwd(remote_dir); lines = []; ftp.dir(lines.append)
            for line in lines:
                parts = line.split(); name = parts[-1]
                if name in [".", ".."]: continue
                is_dir = line.startswith("d")
                local_path = os.path.join(local_dir, name)
                if is_dir:
                    os.makedirs(local_path, exist_ok=True)
                    self._mirror_ftp_dir(ftp, f"{remote_dir}/{name}", local_path)
                    ftp.cwd(remote_dir)
                else:
                    with open(local_path, "wb") as f: ftp.retrbinary(f"RETR {name}", f.write)
        except: pass

class RestoreThread(QThread):
    def __init__(self, ip, items):
        super().__init__(); self.ip = ip; self.items = items; self.port = 2121
    def run(self):
        server_signals.restore_log.emit("🚀 Начало восстановления...")
        try:
            ftp = ftplib.FTP(); ftp.connect(self.ip, self.port, timeout=10); ftp.login()
            total = len(self.items)
            for i, (local_path, remote_path) in enumerate(self.items):
                server_signals.restore_log.emit(f"📤 [{i+1}/{total}] Загрузка: {os.path.basename(local_path)}")
                self.upload_recursive(ftp, local_path, remote_path)
            ftp.quit()
            server_signals.restore_log.emit("✅ Восстановление завершено успешно!")
        except Exception as e: server_signals.restore_log.emit(f"❌ Ошибка восстановления: {str(e)}")
        finally: server_signals.restore_finished.emit()

    def ensure_remote_dir(self, ftp, remote_dir):
        if remote_dir == "/" or remote_dir == "": return
        try: ftp.cwd(remote_dir)
        except:
            parent = os.path.dirname(remote_dir)
            self.ensure_remote_dir(ftp, parent)
            try: ftp.mkd(remote_dir)
            except: pass
            ftp.cwd(remote_dir)

    def upload_recursive(self, ftp, local_path, remote_base):
        self.ensure_remote_dir(ftp, remote_base)
        for root, dirs, files in os.walk(local_path):
            rel_path = os.path.relpath(root, local_path)
            if rel_path == ".": rel_path = ""
            current_remote = f"{remote_base}/{rel_path}".replace("\\", "/") if rel_path else remote_base
            self.ensure_remote_dir(ftp, current_remote)
            for f in files:
                with open(os.path.join(root, f), "rb") as file_obj: ftp.storbinary(f"STOR {f}", file_obj)

# --- GLOBAL CONSTANTS & STYLES ---
DEPTH_COLORS_DARK = ["#FFD700", "#FF8C00", "#00BFFF", "#DA70D6", "#3CB371"] 
DEPTH_COLORS_LIGHT = ["#D35400", "#C0392B", "#2980B9", "#8E44AD", "#27AE60"]

STATUS_STYLES = {
    "NotInstalled": "background-color: #4B0082; color: white; margin: 0px;",
    "Installed": "background-color: #008000; color: white; margin: 0px;",
    "AlreadyInstalled": "background-color: #006400; color: white; margin: 0px;",
    "Installing": "background-color: #DAA520; color: black; margin: 0px;",
    "Paused": "background-color: #FF4500; color: white; margin: 0px;",
    "Error": "background-color: #8B0000; color: white; margin: 0px;",
    "Cancelled": "background-color: #333; color: #aaa; margin: 0px;",
    "Skipped": "background-color: #FF8C00; color: white; margin: 0px;"
}
# --- DIALOGS ---

class UpdateDialog(QDialog):
    def __init__(self, parent, new_ver, url, lang):
        super().__init__(parent)
        self.setWindowTitle(LOCALE[lang]["upd_title"])
        self.setFixedWidth(400)
        self.url = url; self.lang = lang
        layout = QVBoxLayout(self)
        lbl = QLabel(LOCALE[lang]["upd_msg"].format(new_ver))
        lbl.setWordWrap(True); layout.addWidget(lbl)
        self.progress = QProgressBar(); self.progress.setVisible(False); layout.addWidget(self.progress)
        btns = QHBoxLayout()
        self.btn_update = QPushButton(LOCALE[lang]["upd_btn"])
        self.btn_update.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px;")
        self.btn_update.clicked.connect(self.start_update)
        btn_cancel = QPushButton(LOCALE[lang]["upd_skip"])
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_update); btns.addWidget(btn_cancel); layout.addLayout(btns)
    def start_update(self):
        self.btn_update.setEnabled(False); self.progress.setVisible(True); self.progress.setValue(0)
        new_exe = os.path.join(os.path.dirname(sys.executable), "update_temp.exe")
        self.downloader = UpdateDownloaderThread(self.url, new_exe)
        server_signals.update_progress.connect(self.progress.setValue)
        server_signals.update_finished.connect(self.on_download_finished)
        self.downloader.start()
    def on_download_finished(self, path):
        if path: self.install_update(path)
        else: QMessageBox.critical(self, "Error", LOCALE[self.lang]["upd_err"]); self.reject()
    def install_update(self, new_path):
        current_exe = sys.executable; folder = os.path.dirname(current_exe); bat_path = os.path.join(folder, "updater.bat"); pid = os.getpid()
        cmds = f"""@echo off\ntimeout /t 2 /nobreak > NUL\n:loop\ntasklist /FI "PID eq {pid}" 2>NUL | find /I /N "{pid}" >NUL\nif "%ERRORLEVEL%"=="0" (\n    timeout /t 1 >NUL\n    goto loop\n)\ntimeout /t 1 /nobreak >NUL\nmove /y "{new_path}" "{current_exe}" > NUL\nstart "" explorer "{current_exe}"\ndel "%~f0"\n"""
        try:
            with open(bat_path, "w") as f: f.write(cmds)
            subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
            
            # Сообщаем главному окну, что идет обновление, чтобы пропустить диалог закрытия
            if self.parentWidget() and hasattr(self.parentWidget(), 'is_updating'):
                 self.parentWidget().is_updating = True
                 
            QApplication.quit(); sys.exit(0)
        except Exception as e: QMessageBox.critical(self, "Update Error", str(e)); self.reject()

class FirmwareSelectDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Firmware Selection")
        self.setFixedWidth(400)
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Localization
        lang = self.settings.value("language", "en")
        if lang == "ru":
           t_title = "Выбор версии прошивки"
           t_lbl = "Пожалуйста, выберите версию прошивки (целевая):"
           t_chk = "Больше не показывать"
        else:
           t_title = "Firmware Selection"
           t_lbl = "Please select your firmware version (target):"
           t_chk = "Do not show again"
           
        self.setWindowTitle(t_title)
        
        lbl = QLabel(t_lbl)
        lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl)
        
        self.fw_combo = QComboBox()
        # Full List as requested
        full_fws = [
            "5.05", "5.07", "6.50", "6.71", "6.72", "7.00", "7.02", "7.35", 
            "7.50", "7.55", "8.00", "8.52", "9.00", "9.03", "9.60", "10.00", 
            "10.71", "11.00", "11.02", "11.52", "12.00", "12.02", "12.50", 
            "12.52", "13.00", "13.02"
        ]
        self.fw_combo.addItems(full_fws)
        layout.addWidget(self.fw_combo)
        
        # Load saved selection if exists
        saved_fw = self.settings.value("my_firmware", "")
        if saved_fw:
             idx = self.fw_combo.findText(saved_fw)
             if idx >= 0: self.fw_combo.setCurrentIndex(idx)
        
        self.chk_dont_show = QCheckBox(t_chk)
        self.chk_dont_show.setStyleSheet("""
            QCheckBox { background-color: #d4efdf; padding: 5px; border-radius: 4px; color: #1e8449; font-weight: bold; }
            QCheckBox::indicator { width: 15px; height: 15px; }
        """)
        layout.addWidget(self.chk_dont_show)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        if lang == "ru":
             btns.button(QDialogButtonBox.StandardButton.Ok).setText("ОК")
        btns.accepted.connect(self.save_and_close)
        layout.addWidget(btns)

    def save_and_close(self):
        fw = self.fw_combo.currentText()
        self.settings.setValue("my_firmware", fw)
        if self.chk_dont_show.isChecked():
            self.settings.setValue("suppress_fw_dialog", True)
        self.accept()

class BackupDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle(LOCALE[parent.current_lang]["bkp_title"])
        self.setFixedWidth(550) 
        self.settings = settings
        self.should_force = False
        self.lang = parent.current_lang
        self.init_ui()
    def showEvent(self, event): 
        self.center_on_parent(); super().showEvent(event)
    def center_on_parent(self):
        if self.parent():
            parent_geo = self.parent().geometry(); center_point = parent_geo.center()
            frame_geo = self.frameGeometry(); frame_geo.moveCenter(center_point); self.move(frame_geo.topLeft())
    def t(self, key): return LOCALE.get(self.lang, LOCALE["en"]).get(key, key)
    def init_ui(self):
        layout = QVBoxLayout(self)
        grp = QGroupBox(LOCALE[self.lang]["bkp_grp"])
        grp_layout = QFormLayout(grp)
        self.chk_enable = QCheckBox(LOCALE[self.lang]["bkp_enable"])
        self.chk_enable.setChecked(self.settings.value("backup_enabled", False, type=bool))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setText(self.settings.value("backup_path", ""))
        self.path_edit.setPlaceholderText("...")
        btn_path = QPushButton("...")
        btn_path.setFixedWidth(30)
        btn_path.clicked.connect(self.choose_path)
        path_layout.addWidget(self.path_edit); path_layout.addWidget(btn_path)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440); self.interval_spin.setSuffix(" min")
        self.interval_spin.setValue(int(self.settings.value("backup_interval", 60)))
        
        self.interval_spin.setStyleSheet(SPINBOX_FIX)
        
        grp_layout.addRow(self.chk_enable)
        grp_layout.addRow(LOCALE[self.lang]["bkp_path"], path_layout)
        grp_layout.addRow(LOCALE[self.lang]["bkp_int"], self.interval_spin)
        self.btn_manual = QPushButton(LOCALE[self.lang]["bkp_run"])
        self.btn_manual.setStyleSheet("background-color: #27ae60; color: white; padding: 6px; font-weight: bold;")
        self.btn_manual.clicked.connect(self.force_start)
        grp_layout.addRow(self.btn_manual)
        info = QLabel(LOCALE[self.lang]["bkp_info"])
        info.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(grp); layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("cancel"))
        buttons.accepted.connect(self.save_and_close); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def choose_path(self):
        d = QFileDialog.getExistingDirectory(self, "Dir")
        if d: self.path_edit.setText(d)
    def force_start(self): self.should_force = True; self.save_and_close()
    def save_and_close(self):
        self.settings.setValue("backup_enabled", self.chk_enable.isChecked())
        self.settings.setValue("backup_path", self.path_edit.text())
        self.settings.setValue("backup_interval", self.interval_spin.value())
        self.accept()

class RestoreDialog(QDialog):
    def __init__(self, parent=None, ip="", settings=None):
        super().__init__(parent); self.lang = parent.current_lang
        self.setWindowTitle(self.t("rest_title")); self.resize(900, 600) 
        self.ps4_ip = ip; self.settings = settings; self.selected_items_to_restore = [] 
        if self.settings and self.settings.value("restore_geometry"): self.restoreGeometry(self.settings.value("restore_geometry"))
        self.init_ui(); server_signals.username_found.connect(self.update_username)
    def t(self, key): return LOCALE.get(self.lang, LOCALE["en"]).get(key, key)
    def t(self, key): return LOCALE.get(self.lang, LOCALE["en"]).get(key, key)
    def showEvent(self, event): self.center_on_parent(); super().showEvent(event)
    def center_on_parent(self):
        if self.parent():
            parent_geo = self.parent().geometry(); center_point = parent_geo.center()
            frame_geo = self.frameGeometry(); frame_geo.moveCenter(center_point); self.move(frame_geo.topLeft())
    def init_ui(self):
        layout = QVBoxLayout(self); top = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText("..."); self.path_edit.setReadOnly(True)
        btn_browse = QPushButton(LOCALE[self.lang]["rest_browse"]); btn_browse.clicked.connect(self.browse_backup)
        top.addWidget(self.path_edit); top.addWidget(btn_browse); layout.addLayout(top)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels([LOCALE[self.lang]["rest_col1"], LOCALE[self.lang]["rest_col2"]])
        self.grid_delegate = GridDelegate(parent=self.tree); self.tree.setItemDelegate(self.grid_delegate)
        self.tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter); self.tree.setAlternatingRowColors(True); self.tree.setColumnWidth(0, 250) 
        if self.settings:
            w0 = self.settings.value("restore_col_0", 250)
            if int(w0) > 0: self.tree.setColumnWidth(0, int(w0))
        layout.addWidget(self.tree)
        self.btn_send = QPushButton(LOCALE[self.lang]["rest_send"])
        self.btn_send.setStyleSheet("background-color: #27ae60; color: white; padding: 8px; font-weight: bold; font-size: 14px;")
        self.btn_send.clicked.connect(self.start_restore); self.btn_send.setEnabled(False); layout.addWidget(self.btn_send)
    def closeEvent(self, e):
        if self.settings:
            self.settings.setValue("restore_geometry", self.saveGeometry()); self.settings.setValue("restore_col_0", self.tree.columnWidth(0))
        super().closeEvent(e)
    def browse_backup(self):
        default_path = ""; 
        if self.settings: default_path = self.settings.value("backup_path", "")
        d = QFileDialog.getExistingDirectory(self, "Select Backup", default_path)
        if d:
            if os.path.exists(os.path.join(d, "user", "home")):
                self.path_edit.setText(d); self.scan_backup(d); self.btn_send.setEnabled(True); self.resolve_ps4_usernames()
            else: QMessageBox.warning(self, "Error", "Structure '/user/home' not found.")
    def scan_backup(self, root_path):
        self.tree.clear(); user_home = os.path.join(root_path, "user", "home")
        try:
            users = os.scandir(user_home)
            for u in users:
                if u.is_dir():
                    user_item = QTreeWidgetItem(self.tree); user_item.setText(0, f"👤 User: {u.name}")
                    user_item.setFlags(user_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                    user_item.setCheckState(0, Qt.CheckState.Checked); user_item.setData(0, Qt.ItemDataRole.UserRole + 10, u.name)
                    savedata_path = os.path.join(u.path, "savedata")
                    if os.path.exists(savedata_path):
                        titles = os.scandir(savedata_path)
                        for t in titles:
                            if t.is_dir():
                                t_item = QTreeWidgetItem(user_item); t_item.setText(0, f"🎮 {t.name}"); t_item.setText(1, t.path)
                                t_item.setFlags(t_item.flags() | Qt.ItemFlag.ItemIsUserCheckable); t_item.setCheckState(0, Qt.CheckState.Checked)
                                remote_path = f"/user/home/{u.name}/savedata/{t.name}"; t_item.setData(0, Qt.ItemDataRole.UserRole, (t.path, remote_path))
            self.tree.expandAll()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))
    def resolve_ps4_usernames(self):
        uids = []; root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i); uid = item.data(0, Qt.ItemDataRole.UserRole + 10)
            if uid: uids.append(uid)
        if uids and self.ps4_ip: threading.Thread(target=self._fetch_names, args=(uids, self.ps4_ip), daemon=True).start()
    def _fetch_names(self, uids, ip):
        try:
            ftp = ftplib.FTP(ip, port=2121, timeout=3); ftp.login()
            for uid in uids:
                try:
                    path = f"/system_data/priv/home/{uid}/username.dat"; buf = io.BytesIO()
                    ftp.retrbinary(f"RETR {path}", buf.write); raw = buf.getvalue()
                    name = raw.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                    if name: server_signals.username_found.emit(uid, name)
                except: pass
            ftp.quit()
        except: pass
    def update_username(self, uid, name):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i); item_uid = item.data(0, Qt.ItemDataRole.UserRole + 10)
            if item_uid == uid: item.setText(0, f"👤 User: {name} ({uid})")
    def start_restore(self):
        self.selected_items_to_restore = []; it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data: self.selected_items_to_restore.append(data)
            it += 1
        if not self.selected_items_to_restore: QMessageBox.warning(self, "Attention", "Nothing selected!"); return
        self.accept()

# --- FTP SEARCH THREAD ---
class FTPSearchThread(QThread):
    found_signal = pyqtSignal(list)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, ip, start_path, pattern):
        super().__init__()
        self.ip = ip
        self.start_path = start_path
        self.pattern = pattern.lower()
        self.is_running = True
        self.ftp = None

    def stop(self):
        self.is_running = False
        try:
            if self.ftp: self.ftp.abort()
        except: pass

    def run(self):
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.ip, 2121, timeout=10)
            self.ftp.login()
            self.ftp.set_pasv(True)
            
            self._walk(self.start_path)
            
            self.finished_signal.emit()
            try: self.ftp.quit()
            except: pass
        except Exception as e:
            if self.is_running:
                self.error_signal.emit(str(e))

    def _walk(self, path):
        if not self.is_running: return
        
        try:
            files = []
            try:
                self.ftp.cwd(path)
                lines = []
                self.ftp.retrlines('LIST', lines.append)
            except: return

            for line in lines:
                if not self.is_running: return
                # Very basic parsing for name and type logic
                parts = line.split(None, 8)
                if len(parts) < 9: continue
                
                name = parts[8]
                is_dir = line.startswith('d')
                full_path = os.path.join(path, name).replace('\\', '/')
                
                if self.pattern in name.lower():
                    # Format: (name, is_dir, size, date, full_path)
                    size = parts[4] if not is_dir else ""
                    # Date is usually parts[5:8]
                    date_str = " ".join(parts[5:8])
                    self.found_signal.emit([(name, is_dir, size, date_str, full_path)])
                
                if is_dir and name not in [".", ".."]:
                    self._walk(full_path)
        except: pass

# --- CLOSE OPTION DIALOG (NEW) ---
class CloseOptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = parent.current_lang if parent else "ru"
        self.setWindowTitle(LOCALE[self.lang]["confirm_title"])
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.result_code = 0 
        layout = QVBoxLayout(self)
        self.frame = QFrame(); self.frame.setObjectName("dialogFrame")
        self.frame.setStyleSheet("""QFrame#dialogFrame { border: 1px solid #444; border-radius: 8px; background-color: palette(window); }""")
        frame_layout = QVBoxLayout(self.frame); frame_layout.setContentsMargins(20, 20, 20, 20); frame_layout.setSpacing(15)
        
        lbl_text = self.t("confirm_exit_text")
        lbl = QLabel(lbl_text); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setStyleSheet("font-size: 14px; font-weight: bold; border: none; background: transparent;")
        frame_layout.addWidget(lbl)
        
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(15)
        btn_exit = QPushButton(self.t("btn_exit"))
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor); btn_exit.setMinimumHeight(35)
        btn_exit.setStyleSheet("QPushButton { background-color: #c0392b; color: white; border: 1px solid #962d22; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #e74c3c; }")
        btn_exit.clicked.connect(self.on_exit)
        
        btn_tray = QPushButton(self.t("btn_tray"))
        btn_tray.setCursor(Qt.CursorShape.PointingHandCursor); btn_tray.setMinimumHeight(35)
        btn_tray.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: 1px solid #1e8449; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #2ecc71; }")
        btn_tray.clicked.connect(self.on_tray)
        
        btn_layout.addWidget(btn_exit); btn_layout.addWidget(btn_tray); frame_layout.addLayout(btn_layout)
        
        btn_cancel = QPushButton(self.t("cancel"))
        btn_cancel.setFlat(True); btn_cancel.setStyleSheet("color: #aaa; text-decoration: underline; border: none;")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor); btn_cancel.clicked.connect(self.reject)
        frame_layout.addWidget(btn_cancel, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frame)

    def t(self, key):
        return LOCALE.get(self.lang, LOCALE["ru"]).get(key, key)

    def on_exit(self): self.result_code = 1; self.accept()
    def on_tray(self): self.result_code = 2; self.accept()

# --- MAIN WINDOW ---
class DragDropLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    self.setText(path)
                else:
                    self.setText(os.path.dirname(path))
            event.acceptProposedAction()

# --- BACKPORT ENGINE ---

class ElfPatcher:
    """
    Handles patching of PS4 ELF files (eboot.bin, *.prx) to downgrade SDK version.
    Allows new games to run on old firmware.
    """
    def __init__(self, target_fw_ver):
        self.target_ver_hex = self._fw_to_hex(target_fw_ver)
        self.patch_count = 0

    def _fw_to_hex(self, fw_ver):
        """Convert '5.05' -> 0x05050000"""
        try:
            parts = fw_ver.split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            # format: MM mm 00 00
            return (major << 24) | (minor << 16)
        except:
            return 0x05050000 # Default fallback

    def patch_file(self, file_path):
        """Scans an ELF file and patches the SDK version in PT_NOTE."""
        try:
            with open(file_path, "r+b") as f:
                # 1. READ ELF HEADER (64-bit)
                # e_ident (16), e_type (2), e_machine (2), e_version (4), e_entry (8)
                # e_phoff (8), e_shoff (8), e_flags (4), e_ehsize (2), e_phentsize (2)
                # e_phnum (2) ...
                
                f.seek(0)
                magic = f.read(4)
                
                # DEBUG: Log magic for analysis
                # log(f"Scanning: {os.path.basename(file_path)} Magic: {magic.hex()}", "DEBUG")
                
                # Check for Retail (Encrypted) SELF
                if magic == b'\x53\x43\x45\x00': # SCE\0
                    log(f"Encrypted Retail Binary (SELF) detected: {os.path.basename(file_path)}", "WARN")
                    
                    # FIX: Automated Decryption via unfself.exe
                    tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
                    unfself_path = os.path.join(tools_dir, "unfself.exe")
                    
                    if os.path.exists(unfself_path):
                         log("Found unfself.exe. Attempting auto-decryption...", "INFO")
                         temp_elf = file_path + ".decrypted"
                         
                         # unfself.exe <input> <output>
                         cmd_decrypt = f'"{unfself_path}" "{file_path}" "{temp_elf}"'
                         
                         try:
                             # Use Popen to hide window
                             si = subprocess.STARTUPINFO()
                             si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                             subprocess.check_call(cmd_decrypt, startupinfo=si)
                             
                             if os.path.exists(temp_elf) and os.path.getsize(temp_elf) > 0:
                                 # Replace original with decrypted
                                 f.close() # Close handle before replace
                                 shutil.move(temp_elf, file_path)
                                 log("Decryption successful! Proceeding with patch...", "INFO")
                                 return self.patch_file(file_path) # Recursively patch the now-decrypted ELF
                             else:
                                 log("Decryption failed (output empty/missing).", "ERROR")
                         except Exception as exc:
                             log(f"Auto-decryption error: {exc}", "ERROR")
                    else:
                        log("Cannot patch encrypted file. 'unfself.exe' not found in tools/.", "ERROR")
                        # Only show alert if we are in GUI context? For now just log.
                    
                    return False
                    
                if magic != b'\x7fELF': return False # Not an ELF
                
                f.seek(0x20) # e_phoff (Program Header Offset)
                e_phoff = struct.unpack('<Q', f.read(8))[0]
                
                f.seek(0x36) # e_phentsize
                e_phentsize = struct.unpack('<H', f.read(2))[0]
                
                f.seek(0x38) # e_phnum
                e_phnum = struct.unpack('<H', f.read(2))[0]
                
                # 2. SCAN PROGRAM HEADERS FOR PT_NOTE (Type 4)
                for i in range(e_phnum):
                    offset = e_phoff + (i * e_phentsize)
                    f.seek(offset)
                    
                    # p_type (4)
                    p_type = struct.unpack('<I', f.read(4))[0]
                    
                    if p_type == 4: # PT_NOTE
                        # Found Note Section!
                        f.seek(offset + 4) # Skip p_type
                        p_flags = struct.unpack('<I', f.read(4))[0]
                        p_offset = struct.unpack('<Q', f.read(8))[0]
                        p_filesz = struct.unpack('<Q', f.read(8))[0]
                        
                        # 3. SCAN NOTES
                        self._scan_notes_and_patch(f, p_offset, p_filesz)
                        
            return True
        except Exception as e:
            log(f"ELF Patch Error ({os.path.basename(file_path)}): {e}", "ERROR")
            return False

    def _scan_notes_and_patch(self, f, offset, size):
        """Iterate through notes to find 'PlayStation 4' -> SDK Version."""
        cur = offset
        end = offset + size
        
        while cur < end:
            f.seek(cur)
            # Note Header: n_namesz (4), n_descsz (4), n_type (4)
            data = f.read(12)
            if len(data) < 12: break
            
            n_namesz, n_descsz, n_type = struct.unpack('<III', data)
            
            # Read Name
            name_bytes = f.read(n_namesz)
            name_str = name_bytes.decode('utf-8', 'ignore').strip('\x00')
            
            # Align padding
            cur += 12 + n_namesz
            if cur % 4 != 0: cur += (4 - (cur % 4))
            
            # Check if it is PS4 Info Note
            if "PlayStation 4" in name_str and n_type == 1:
                # This is it! The descriptor contains the version info.
                # Structure of descriptor:
                # 0x00: fw_version (timestamp?)
                # ...
                # We are looking for the SDK Version. 
                # Usually it is at offset for SDK Ver.
                # PS4 SDK Version is typically at descriptor offset + 0 or + something?
                # Actually, standard PS4 ABI says type 1 description is:
                # struct {
                #   uint64_t firmware_size;
                #   byte     firmware_version[16?]... OR
                #   uint32_t sdk_version; 
                # }
                #
                # Let's simplify: searching for the high version number might be safer if we don't know exact struct.
                # BUT, usually it is:
                # [Unknown 8 bytes] [SDK Version 4 bytes] ...
                
                # Let's try to patch any 4-byte integer that looks like a high FW version
                # if it is greater than our target.
                
                # Read descriptor
                desc_pos = cur # F is already at descriptor start? No, we need to seek
                f.seek(desc_pos)
                
                # NOTE: We just patch the binary directly here?
                # Let's read the first 32 bytes of descriptor, SDK ver usually within.
                desc_data = f.read(n_descsz)
                
                # Simple Heuristic: If we find a version > target, lower it.
                # SDK version 0x09000000 (9.00) vs 0x05050000 (5.05)
                
                # Convert buffer to mutable
                mutable_desc = bytearray(desc_data)
                modified = False
                
                for i in range(0, len(mutable_desc) - 3, 4):
                    val = struct.unpack('<I', mutable_desc[i:i+4])[0]
                    # Check if it looks like a version (e.g., > 1.00 and < 15.00)
                    # 0x01000000 to 0x0F000000
                    if 0x01000000 < val < 0x20000000:
                         if val > self.target_ver_hex:
                             log(f"Patching SDK Ver: {hex(val)} -> {hex(self.target_ver_hex)} at global offset {hex(desc_pos+i)}", "DEBUG")
                             struct.pack_into('<I', mutable_desc, i, self.target_ver_hex)
                             modified = True
                             self.patch_count += 1
                
                if modified:
                    f.seek(desc_pos)
                    f.write(mutable_desc)

            # Move to next note
            cur += n_descsz
            if cur % 4 != 0: cur += (4 - (cur % 4))

    def scan_folder(self, folder_path):
        """Recursively scan folder for ELF files and patch them."""
        log(f"Starting ELF Scan in: {folder_path}", "INFO")
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # FIX: Scan ALL files to detect Retail/Encrypted headers (SCE), not just .prx/eboot
                full_path = os.path.join(root, file)
                self.patch_file(full_path)
        log(f"ELF Patching Finished. Total Patches: {self.patch_count}", "INFO")

class BackportDialog(QDialog):
    def __init__(self, parent=None, target_pkg=""):
        super().__init__(parent)
        # FIX: Localization and Title
        title = self.t("bp_title") if hasattr(self, 't') else "Backport Tool"
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.target_pkg = target_pkg
        if target_pkg:
             self.save_path = os.path.join(os.path.dirname(target_pkg), "BACKPORT")
        else:
             self.save_path = ""
        self.init_ui()
        self.center_on_parent()
        
    def center_on_parent(self):
        """Center the dialog over the parent window."""
        if self.parent() and self.parent().isVisible():
            parent_geo = self.parent().geometry()
            self.move(
                parent_geo.center().x() - self.width() // 2,
                parent_geo.center().y() - self.height() // 2
            )

    def t(self, key):
        # Quick helper to get localized strings from parent
        if self.parent() and hasattr(self.parent(), 't'):
             return self.parent().t(key)
        # Fallback if t doesn't exist
        return key

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info
        lbl_target = QLabel(self.t("bp_target").format(os.path.basename(self.target_pkg)))
        lbl_target.setWordWrap(True)
        layout.addWidget(lbl_target)
        
        # Firmware
        layout.addWidget(QLabel(self.t("bp_fw")))
        
        self.fw_combo = QComboBox()
        # FIX: Full list of firmwares as requested
        self.fw_list = [
            "5.05", "5.07", "6.50", "6.71", "6.72", "7.00", "7.02", "7.35", 
            "7.50", "7.55", "8.00", "8.52", "9.00", "9.03", "9.60", "10.00", 
            "10.71", "11.00", "11.02", "11.52", "12.00", "12.02", "12.50", 
            "12.52", "13.00", "13.02"
        ]
        
        # Labels for dropdown
        items = [self.t("bp_my_list"), self.t("bp_all_fw")] + self.fw_list
        self.fw_combo.addItems(items)
        layout.addWidget(self.fw_combo)
        
        # Output Folder
        layout.addSpacing(5)
        layout.addWidget(QLabel(self.t("bp_save")))
        
        path_layout = QHBoxLayout()
        # USE CUSTOM DRAG DROP EDIT
        self.path_input = DragDropLineEdit(self.save_path)
        self.path_input.setText(self.save_path)
        path_layout.addWidget(self.path_input)
        
        btn_browse = QPushButton(self.t("bp_browse"))
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(btn_browse)
        layout.addLayout(path_layout)
        
        layout.addSpacing(10)
        
        # Actions
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton(self.t("bp_start"))
        self.btn_run.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton(self.t("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder", self.save_path)
        if d: 
            self.save_path = d
            self.path_input.setText(d)

class PasscodeDialog(QDialog):
    def __init__(self, parent=None, default_passcode="00000000000000000000000000000000", target_pkg=""):
        super().__init__(parent)
        self.setWindowTitle(self.t("bp_pass_title"))
        self.setMinimumWidth(500)
        self.passcode = default_passcode
        self.target_pkg = target_pkg
        self.tools_path = resource_path("tools")
        self.init_ui()
        self.center_on_parent()

    def center_on_parent(self):
        """Center the dialog over the parent window."""
        if self.parent() and self.parent().isVisible():
            parent_geo = self.parent().geometry()
            self.move(
                parent_geo.center().x() - self.width() // 2,
                parent_geo.center().y() - self.height() // 2
            )

    def t(self, key):
        if self.parent() and hasattr(self.parent(), 't'):
             return self.parent().t(key)
        return key
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info
        lbl_info = QLabel(self.t("bp_pass_info"))
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.inp_passcode = QLineEdit(self.passcode)
        self.inp_passcode.setMaxLength(32)
        # Font monospace
        font = self.inp_passcode.font()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.inp_passcode.setFont(font)
        
        input_layout.addWidget(self.inp_passcode)
        layout.addLayout(input_layout)
        
        # Extract Button
        btn_extract = QPushButton(self.t("bp_pass_extract"))
        btn_extract.setToolTip(self.t("bp_pass_extract_tip"))
        btn_extract.clicked.connect(self.extract_from_base)
        layout.addWidget(btn_extract)
        
        layout.addSpacing(10)
        
        # Buttons
        btn_box = QDialogButtonBox()
        btn_ok = btn_box.addButton(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText(self.t("ok"))
        btn_cancel = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_cancel.setText(self.t("cancel"))
        
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
    def extract_from_base(self):
        start_dir = os.path.dirname(self.target_pkg) if self.target_pkg else ""
        fname, _ = QFileDialog.getOpenFileName(self, self.t("bp_pass_select_base"), start_dir, "PKG Files (*.pkg)")
        if not fname: return
        
        # Run orbis-pub-cmd img_info
        pub_cmd = os.path.join(self.tools_path, "orbis-pub-cmd.exe")
        if not os.path.exists(pub_cmd):
            QMessageBox.critical(self, self.t("error"), self.t("backport_config_err"))
            return
            
        try:
            # Command: orbis-pub-cmd img_info header "file.pkg"
            # Note: We just run img_info and hope passcode is in output
            cmd = f'"{pub_cmd}" img_info "{fname}"'
            
            # Use startupinfo to hide window
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Run
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si, shell=True)
            out, err = proc.communicate(timeout=15)
            
            output = out.decode(errors='ignore')
            
            # Parse for "Passcode: ..."
            import re
            m = re.search(r"Passcode:\s*([A-Za-z0-9]{32})", output, re.IGNORECASE)
            
            if m:
                found_pass = m.group(1)
                self.inp_passcode.setText(found_pass)
                QMessageBox.information(self, self.t("done"), self.t("bp_pass_found").format(found_pass))
            else:
                # Try fallback: maybe simply grep any 32-char hex string labeled passcode?
                QMessageBox.warning(self, self.t("bp_pass_not_found_title"), self.t("bp_pass_not_found"))
                log(f"img_info output: {output}", "DEBUG")
                
        except Exception as e:
            QMessageBox.critical(self, self.t("error"), f"{self.t('error')}: {e}")

    def get_passcode(self):
        return self.inp_passcode.text().strip()

class MainWindow(QMainWindow):
    ftp_list_signal = pyqtSignal(list, str)
    
    def __init__(self):
        super().__init__()
        # hide_console()  # Disabled per user request
        self.settings = QSettings("StormApp", "STORM_v1215")
        self.current_lang = self.settings.value("language", "ru")
        self.setWindowTitle(LOCALE[self.current_lang]["window_title"])
        
        try:
            icon_path = resource_path("stormps4pkgsender.ico")
            if not os.path.exists(icon_path):
                icon_path = resource_path("stormps4pkgsender.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e: pass
        
        self.setAcceptDrops(True)
        
        # Data Structures
        self.file_map = {}
        self.server_obj = None
        self.rpi_port = 12813, 12800, 12801
        self.install_queue = []
        self.active_installs = [] # List of items currently installing
        self.is_global_paused = False
        self.current_bg_path = ""
        self.pinned_folders = [] 
        self.pinned_data_cache = {}
        self.folder_items_map = {}
        self.backup_thread = None
        self.restore_thread = None
        self.installed_apps_cache = {} 
        self.finished_unique_keys = set() 
        self.added_files_set = set() 
        self.tid_to_item_map = {} # TID -> GAME Item mapper for fast adoption
        
        # Stats Data
        self.file_sizes_map = {} 
        self.progress_map = {} 
        self.speed_map = {} 
        self.bytes_remaining = 0
        self.active_loaders = 0 # Counter for concurrent loader threads
        
        self.server_status_ok = False
        self.server_port_val = 8337
        self.is_connected = False
        self.found_services = {"RPI": False, "FTP": False, "BIN": False}
        self.silent_scanner = None # FIX: Initialize to None
        
        self.countdown_val = 0
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.tick_countdown)
        
        self.temp_backports = {} # storage for cleanup
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_eta_and_speed_labels)
        self.stats_timer.start(1000)
        
        # Keep-Alive Session
        self.http_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        self.http_session.mount('http://', adapter)

        self.is_pinging = False
        self.rpi_port = 12800  # Default RPI port, will be updated to 12813 if SPPI detected
        
        # Mini Mode State
        self.is_mini_mode = False
        self.is_updating = False # Флаг для автоматического закрытия при обновлении
        self.saved_geometry = None
        self.saved_geometry = None
        self.saved_col_widths = []
        
        self.ftp_session = None 
        self.is_processing_queue = False 

        self.init_ui()
        self.ftp_list_signal.connect(self.update_ftp_list_ui)

        self.setup_tray()
        self.load_config()
        self.retranslate_ui()
        
        self.force_taskbar_icon()

        # Connect Global Signals
        server_signals.update_found.connect(self.on_update_found)
        server_signals.update_not_found.connect(self.on_update_not_found)
        server_signals.ping_result.connect(self.handle_ping_result, Qt.ConnectionType.QueuedConnection)
        server_signals.progress.connect(self.update_progress, Qt.ConnectionType.QueuedConnection)
        server_signals.status_msg.connect(self.show_status_msg, Qt.ConnectionType.QueuedConnection)
        server_signals.install_status.connect(self.handle_install_status, Qt.ConnectionType.QueuedConnection)
        server_signals.speed_update.connect(self.update_speed, Qt.ConnectionType.QueuedConnection)
        server_signals.loader_root_created.connect(self.on_loader_root)
        server_signals.loader_file_found.connect(self.on_loader_file)
        server_signals.loader_batch_found.connect(self.on_loader_batch)
        server_signals.loader_finished.connect(self.on_loader_finished)
        server_signals.scan_finished.connect(self.on_scan_finished)
        server_signals.backup_log.connect(self.show_status_msg)
        server_signals.backup_started.connect(self.on_backup_started)
        server_signals.backup_finished.connect(self.on_backup_finished)
        server_signals.restore_log.connect(self.show_status_msg)
        server_signals.restore_finished.connect(self.on_restore_finished)
        
        # FIX: Connect Passcode Request Signal
        server_signals.request_passcode.connect(self.ask_passcode_dialog)
        server_signals.silent_scan_finished.connect(self.on_silent_scan_finished)
        server_signals.apps_scan_finished.connect(self.update_pkg_table)  # PKG Manager
        
        if self.chk_auto_update.isChecked():
            self.check_for_updates()

        QTimer.singleShot(100, self.start_startup_sequence)
        QTimer.singleShot(1000, self.check_firmware_dialog) # Show FW Dialog
        QTimer.singleShot(2000, self.check_vc_redist_installed) # VC++ Check

    def check_firmware_dialog(self, force=False):
        if force or not self.settings.value("suppress_fw_dialog", False, type=bool):
            dlg = FirmwareSelectDialog(self, self.settings)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                 # Refresh settings UI if visible
                 if hasattr(self, 'lbl_my_fw'):
                      fw = self.settings.value("my_firmware", "---")
                      self.lbl_my_fw.setText(f"<b>{fw}</b>")


    def ask_passcode_dialog(self, pkg_path):
        """Show passcode dialog on main thread requested by background thread."""
        try:
            # FIX: Use custom PasscodeDialog
            dlg = PasscodeDialog(self, target_pkg=pkg_path)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                passcode = dlg.get_passcode()
                if len(passcode) == 32:
                    server_signals.passcode_result = passcode
                else:
                    server_signals.passcode_result = None
            else:
                server_signals.passcode_result = None
        except Exception as e:
            log(f"Passcode Dialog Error: {e}", "ERROR")
            server_signals.passcode_result = None
        finally:
            server_signals.passcode_event.set() # Unblock BG thread

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # FIX: Always set an icon before showing to avoid "No Icon set" warning
        icon = self.windowIcon()
        if icon.isNull():
             # Fallback to standard system icon if custom icon missing
             icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        action_show = QAction(self.t("tray_show"), self)
        action_show.triggered.connect(self.toggle_window_visibility)
        tray_menu.addAction(action_show)
        
        action_exit = QAction(self.t("tray_exit"), self)
        action_exit.triggered.connect(QApplication.quit)
        tray_menu.addAction(action_exit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def toggle_window_visibility(self):
        if self.isVisible(): self.hide()
        else: self.showNormal(); self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window_visibility()

    def init_sidebar_ui(self):
        """Initialize the sidebar with navigation buttons."""
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(60)
        self.sidebar.setObjectName("sidebar")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(5, 10, 5, 10)
        self.sidebar_layout.setSpacing(10)
        
        self.sidebar_buttons = []
        sidebar_items = [
             ("📦", "PKG Sender", 0),
             ("📁", "FTP Browser", 1),
             ("🗑", "PKG Manager", 2),
             ("⚙", "Settings", 3),
        ]
        
        for icon, tooltip, page_idx in sidebar_items:
            btn = QPushButton(icon)
            btn.setFixedSize(50, 50)
            btn.setToolTip(tooltip)
            btn.setObjectName("sidebarBtn")
            btn.setProperty("page_idx", page_idx)
            btn.clicked.connect(lambda checked, idx=page_idx: self.switch_page(idx))
            self.sidebar_layout.addWidget(btn)
            self.sidebar_buttons.append(btn)
            
        self.sidebar_layout.addStretch(1)

    # keyPressEvent removed to fix ambiguous shortcut overload
    # The individual widgets (Tree, FTP) now handle their own shortcuts via QAction/QShortcut context.

    def closeEvent(self, event):
        """Handle application closure and cleanup."""
        # Use centralized cleanup
        try:
             setting_val = self.settings.value("cleanup_backports", True, type=bool)
             perform_cleanup(setting_val)
        except: pass
        
        event.accept()

    def init_ui(self):
        self.setWindowTitle(self.t("window_title"))
        self.resize(1000, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.root_layout = QHBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        # Sidebar
        self.init_sidebar_ui()
        self.root_layout.addWidget(self.sidebar)
        
        # === STACKED WIDGET (Pages) ===
        self.page_stack = QStackedWidget()
        self.root_layout.addWidget(self.page_stack)
        
        # Page 0: PKG Sender
        self.pkg_sender_page = QWidget()
        self.init_pkg_sender_ui() # Calls setup for Page 0 including eta_label
        self.page_stack.addWidget(self.pkg_sender_page)
        
        # Page 1: FTP Browser
        self.ftp_browser_page = QWidget()
        self.init_ftp_ui()
        self.page_stack.addWidget(self.ftp_browser_page)
        
        # Page 2: PKG Manager
        self.pkg_manager_page = QWidget()
        self.init_pkg_manager_ui()
        self.page_stack.addWidget(self.pkg_manager_page)
        
        # Page 3: Settings
        self.settings_page = QWidget()
        self.init_settings_ui()
        self.page_stack.addWidget(self.settings_page)
        
        # Highlight first button
        self.update_sidebar_active(0)

        # Top Panel (Overlays or integrated?) 
        # In current design, Top Panel is PART of `pkg_sender_page`? NO.
        # It seems Top Panel was separate in `view_file`.
        # Wait, `pkg_sender_page` layout usually contains `top_panel`?
        # Let's verify where `top_panel_widget` goes.
        # In previous code, `top_layout` was added to... nothing? 
        # Ah, lines 1602-1642 create `top_panel_widget` but don't add it!
        # It must be added to `pkg_sender_page` layout!
        
        # Let's fix structure. `init_pkg_sender_ui` usually builds the page.
        # So I shouldn't duplicate Top Panel creation here if `init_pkg_sender_ui` does it.
        # Check `init_pkg_sender_ui` content via view_file if unsure?
        # Assuming `init_pkg_sender_ui` does NOT exist or was empty?
        # I'll Assume `top_panel` logic BELONGS in `init_pkg_sender_ui` or at top of page 0.
        
        # BUT I will execute the creation here, and then `init_pkg_sender_ui` handles the rest?
        # Better: Put top panel logic INTO `init_pkg_sender_ui` or add it to page 0 layout.
        
        # RE-CREATING TOP PANEL HERE and assigning to `self`
        self.top_panel_widget = QWidget()
        self.top_layout = QHBoxLayout(self.top_panel_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_ip = QLabel("PS4 IP:")
        self.ip_input = QComboBox()
        self.ip_input.setEditable(True)
        self.ip_input.setFixedWidth(140)
        self.ip_input.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ip_input.lineEdit().setPlaceholderText("IP")
        self.ip_input.setItemDelegate(CenterDelegate(self.ip_input))
        
        self.port_input = QLineEdit()
        self.port_input.setFixedWidth(50)
        self.port_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.port_input.blockSignals(True) # Prevent signal
        self.port_input.setText("8337")
        self.port_input.blockSignals(False)
        self.port_input.textChanged.connect(self.start_server)
        
        self.conn_dot = QLabel("●")
        self.conn_dot.setStyleSheet("color: red; font-size: 18px;")
        
        self.conn_text = QLabel("Не в сети")
        self.conn_text.setStyleSheet("color: red; font-weight: bold;")

        self.btn_check = QPushButton("🔗")
        self.btn_check.clicked.connect(self.ping_ps4)
        self.btn_scan = QPushButton("🌐")
        self.btn_scan.clicked.connect(self.scan_network)
        
        self.top_layout.addWidget(self.lbl_ip); self.top_layout.addWidget(self.ip_input); self.top_layout.addWidget(self.port_input)
        self.top_layout.addWidget(self.conn_dot); self.top_layout.addWidget(self.conn_text); self.top_layout.addWidget(self.btn_check); self.top_layout.addWidget(self.btn_scan)
        self.top_layout.addStretch(1)

        self.chk_overwrite = QCheckBox("Overwrite")
        self.chk_hide_pinned = QCheckBox("Hide Pinned")
        self.chk_hide_pinned.stateChanged.connect(self.update_pinned_visibility)
        self.chk_large_font = QCheckBox("Large Font")
        self.chk_large_font.clicked.connect(self.on_large_font_toggled)

        self.top_layout.addWidget(self.chk_overwrite); self.top_layout.addWidget(self.chk_hide_pinned); self.top_layout.addWidget(self.chk_large_font)
        self.top_layout.addStretch(1)
        
        self.btn_backup = QPushButton("💾")
        self.btn_backup.clicked.connect(self.open_backup_settings)
        self.top_layout.addWidget(self.btn_backup)

        self.btn_restore = QPushButton("♻")
        self.btn_restore.clicked.connect(self.open_restore_dialog)
        self.top_layout.addWidget(self.btn_restore)
        
        # Add Top Panel to Page 0 Layout (Prepending)
        # Assuming init_pkg_sender_ui creates `self.sender_layout` or similar
        # Since I called init_pkg_sender_ui above, check if layout exists.
        if self.pkg_sender_page.layout():
            self.pkg_sender_page.layout().insertWidget(0, self.top_panel_widget)
        else:
             # If no layout, create one
             l = QVBoxLayout(self.pkg_sender_page)
             l.addWidget(self.top_panel_widget)
             l.addStretch()

        self.btn_logs = QPushButton("📋")
        self.btn_logs.setToolTip("Логи / Logs")
        self.btn_logs.clicked.connect(self.show_logs_dialog)
        self.top_layout.addWidget(self.btn_logs)


        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setMinimumWidth(150)
        self.theme_combo.currentTextChanged.connect(self.update_style)
        self.top_layout.addWidget(self.theme_combo)
        
        self.btn_bg = QPushButton("🖼")
        self.btn_bg.setFixedWidth(30)
        self.btn_bg.setObjectName("iconBtn")
        self.btn_bg.clicked.connect(self.set_background_image)
        self.top_layout.addWidget(self.btn_bg)
        
        self.btn_clear_bg = QPushButton("❌")
        self.btn_clear_bg.setFixedWidth(30)
        self.btn_clear_bg.setObjectName("iconBtn")
        self.btn_clear_bg.clicked.connect(self.clear_background)
        self.top_layout.addWidget(self.btn_clear_bg)


        # Add Menu
        self.btn_add_menu = QPushButton(self.t("btn_add_main")) 
        self.btn_add_menu.setFixedWidth(140)
        self.add_menu = QMenu(self.btn_add_menu)
        self.act_add_files = QAction(self.t("menu_add_files"), self) 
        self.act_add_files.triggered.connect(self.select_files)
        self.act_add_folder = QAction(self.t("menu_add_folder"), self) 
        self.act_add_folder.triggered.connect(self.select_folder)
        self.add_menu.addAction(self.act_add_files)
        self.add_menu.addAction(self.act_add_folder)
        self.btn_add_menu.setMenu(self.add_menu)
        
        self.top_layout.addWidget(self.btn_add_menu)
    def init_pkg_sender_ui(self):
        """Initialize Page 0: PKG Sender UI (Tree, Stats, Bottom Panel)."""
        # Ensure layout exists
        if not self.pkg_sender_page.layout():
             self.main_layout = QVBoxLayout(self.pkg_sender_page)
        else:
             self.main_layout = self.pkg_sender_page.layout()

        # Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(11) # 10 visible + 1 hidden for sorting
        self.tree.setColumnHidden(10, True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # HOTKEYS via QAction (Standard Qt Way)
        # Select All (Ctrl+A)
        self.act_sel_all = QAction("Select All", self)
        self.act_sel_all.setShortcut(QKeySequence("Ctrl+A"))
        self.act_sel_all.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_sel_all.triggered.connect(self.tree.selectAll)
        self.tree.addAction(self.act_sel_all)
        
        # Delete (Del)
        self.act_del = QAction("Delete", self)
        self.act_del.setShortcut(QKeySequence("Delete"))
        self.act_del.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_del.triggered.connect(self.delete_selected)
        self.tree.addAction(self.act_del)
        
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_menu)
        self.tree.itemClicked.connect(self.on_item_clicked)

        self.tree.itemDoubleClicked.connect(self.on_item_dbl_clicked)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(30)
        
        # Drag & Drop Support
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.model().rowsMoved.connect(self.restore_widgets_after_drag)
        
        self.grid_delegate = GridDelegate(height=30)
        self.tree.setItemDelegate(self.grid_delegate)
        self.tree.itemCollapsed.connect(self.on_item_collapsed)
        self.tree.itemExpanded.connect(self.on_item_expanded)
        
        # --- TABLE COLUMNS: Fill full width, last column stretches ---
        h = self.tree.header()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(False) 
        h.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch) # Last column (Actions) stretches
        h.setMinimumSectionSize(80) 
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Default column widths for 10 columns: File, TID, Ver, Size, Region, Category, Speed, Progress, Status, Actions
        default_widths = [250, 85, 50, 70, 50, 60, 70, 70, 110, 100]
        saved_widths = self.settings.value("column_widths", "")
        if saved_widths:
            try:
                widths = [int(w) for w in saved_widths.split(",")]
                if len(widths) == 10:
                    default_widths = widths
                    if default_widths[9] < 100: default_widths[9] = 100
            except: pass
        
        for i, w in enumerate(default_widths):
            self.tree.setColumnWidth(i, w)
        
        # Save column widths when resized
        h.sectionResized.connect(self.save_column_widths)
        
        # Column visibility context menu
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self.show_column_visibility_menu)
        
        # Restore column visibility from settings
        self.column_names = [self.t("col_file"), self.t("col_tid"), self.t("col_ver"), self.t("col_size"),
                             self.t("col_region"), self.t("col_category"),
                             self.t("col_speed"), self.t("col_prog"), self.t("col_status"), self.t("col_act")]
        saved_visibility = self.settings.value("column_visibility", "")
        if saved_visibility:
            try:
                visibility = [v == "1" for v in saved_visibility.split(",")]
                if len(visibility) == 10:
                    for i, visible in enumerate(visibility):
                        if not visible:
                            self.tree.setColumnHidden(i, True)
                        else:
                            self.tree.setColumnHidden(i, False)
            except: pass
        else:
             # Default: ensure all visible if no setting
             for i in range(10): self.tree.setColumnHidden(i, False)
        
        # Save column widths when resized
        h.sectionResized.connect(self.save_column_widths)
        
        self.main_layout.addWidget(self.tree)

        # Bottom Panel
        self.bottom_panel_widget = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_panel_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)
        
        # 1. Свернуть все
        self.btn_collapse_all = QPushButton()
        self.btn_collapse_all.clicked.connect(self.tree.collapseAll)
        
        # 2. Развернуть все
        self.btn_expand_all = QPushButton()
        self.btn_expand_all.clicked.connect(self.tree.expandAll)
        
        # 3. Пауза все
        self.btn_global_pause = QPushButton()
        self.btn_global_pause.setCheckable(True)
        self.btn_global_pause.toggled.connect(self.toggle_global_pause)
        # Убрали setStyleSheet, теперь стиль берется из глобальной темы (как у верхних кнопок)
        
        # 4. Отменить все
        self.btn_cancel_all = QPushButton()
        self.btn_cancel_all.clicked.connect(self.cancel_all_operations)
        # Убрали setStyleSheet

        # 5. Отправить все (Самая широкая)
        self.btn_all = QPushButton()
        self.btn_all.setFixedHeight(36) 
        self.btn_all.clicked.connect(self.install_all)
        # Убрали setStyleSheet
        
        self.chk_auto_update = QCheckBox(self.t("auto_update"))
        self.chk_auto_update.setChecked(self.settings.value("auto_update", True, type=bool))
        self.chk_auto_update.clicked.connect(self.save_auto_update_setting)

        self.lang_combo = QComboBox(); self.lang_combo.addItems(["🇷🇺 Русский", "🇺🇸 English"])
        self.lang_combo.setItemDelegate(CenterDelegate(self.lang_combo))
        idx = 0 if self.current_lang == "ru" else 1
        self.lang_combo.setCurrentIndex(idx); self.lang_combo.setFixedWidth(110)
        self.lang_combo.currentIndexChanged.connect(self.switch_language)

        # ДОБАВЛЕНИЕ В LAYOUT
        # Кнопки управления (узкие, stretch=1)
        bottom_layout.addWidget(self.btn_collapse_all, 1)
        bottom_layout.addWidget(self.btn_expand_all, 1)
        bottom_layout.addWidget(self.btn_global_pause, 1)
        bottom_layout.addWidget(self.btn_cancel_all, 1)
        
        # Кнопка отправки (широкая, stretch=5)
        bottom_layout.addWidget(self.btn_all, 5) 
        
        bottom_layout.addWidget(self.chk_auto_update)
        bottom_layout.addWidget(self.lang_combo)
        
        self.main_layout.addWidget(self.bottom_panel_widget)

        # Stats Bar
        self.global_progress_layout = QHBoxLayout(); self.global_progress_layout.setSpacing(10)
        self.global_progress = QProgressBar(); self.global_progress.setTextVisible(True); self.global_progress.setFixedHeight(22)
        
        stats_container = QWidget(); stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0); stats_layout.setSpacing(5)
        
        # ИЗМЕНЕНИЕ: Применяем statsLabel ко всем трем элементам для единого стиля
        self.global_stats_label = QLabel(LOCALE[self.current_lang]["waiting"])
        self.global_stats_label.setObjectName("statsLabel") 
        
        self.size_stats_label = QLabel("Size: 0 / 0")
        self.size_stats_label.setObjectName("statsLabel")
        
        self.eta_label = QLabel("Осталось времени: --:--")
        self.eta_label.setObjectName("statsLabel")
        
        stats_layout.addWidget(self.global_stats_label)
        stats_layout.addWidget(self.size_stats_label)
        stats_layout.addWidget(self.eta_label)
        
        self.global_progress_layout.addWidget(self.global_progress, 1)
        self.global_progress_layout.addWidget(stats_container, 0)      
        self.main_layout.addLayout(self.global_progress_layout)

        self.status_frame = QFrame(); self.status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(self.status_frame); status_layout.setContentsMargins(5, 2, 5, 2)
        self.lbl_sys = QLabel(LOCALE[self.current_lang]["ready"]); self.lbl_sys.setStyleSheet("font-size: 11px;")
        self.lbl_srv = QLabel(LOCALE[self.current_lang]["server_off"]); self.lbl_srv.setStyleSheet("font-size: 11px;")
        status_layout.addWidget(self.lbl_sys); status_layout.addStretch(); status_layout.addWidget(self.lbl_srv)
        self.main_layout.addWidget(self.status_frame)

        # Compact Mode Toggle Button
        self.mini_toggle_container = QWidget()
        mini_toggle_layout = QHBoxLayout(self.mini_toggle_container)
        mini_toggle_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_mini = QPushButton("🔽")
        self.btn_mini.setToolTip(self.t("mini_mode"))
        self.btn_mini.setFixedSize(30, 30)
        self.btn_mini.clicked.connect(self.toggle_mini_mode)
        mini_toggle_layout.addWidget(self.btn_mini)
        
        # Add to main layout of Page 0 – it will stay visible if we hide other panels
        self.main_layout.addWidget(self.mini_toggle_container, 0, Qt.AlignmentFlag.AlignRight)
        
        # Central Widget was set in init_ui, no need to set here

    def init_ftp_ui(self):
        """Initialize FTP Browser UI."""
        layout = QVBoxLayout(self.ftp_browser_page)
        
        # --- Top Toolbar ---
        top_bar = QHBoxLayout()
        
        # Local Path & Drives
        top_bar.addWidget(QLabel(self.t("ftp_pc")))
        
        self.ftp_drives = QComboBox()
        self.ftp_drives.setFixedWidth(60)
        self.ftp_drives.currentIndexChanged.connect(self.ftp_drive_changed)
        top_bar.addWidget(self.ftp_drives)
        
        # Local Path (ComboBox)
        self.ftp_local_path = QComboBox()
        self.ftp_local_path.setEditable(True)
        self.ftp_local_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ftp_local_path.addItem(os.getcwd())
        # Connect signal later to avoid trigger on init
        top_bar.addWidget(self.ftp_local_path, 1)
        
        btn_local_refresh = QPushButton("🔄")
        btn_local_refresh.setFixedSize(30, 30)
        btn_local_refresh.setToolTip(self.t("ftp_refresh"))
        btn_local_refresh.clicked.connect(self.ftp_load_local)
        top_bar.addWidget(btn_local_refresh)
        
        # Remote Path & Presets
        top_bar.addWidget(QLabel(self.t("ftp_ps4")))
        
        self.ftp_remote_path = QComboBox()
        self.ftp_remote_path.setEditable(True)
        self.ftp_remote_path.addItems(["/user/app/", "/user/appmeta/", "/mnt/sandbox/pfsmnt/", "/data/", "/mnt/usb0/"])
        self.ftp_remote_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Connect signal later
        top_bar.addWidget(self.ftp_remote_path, 1)
        
        self.btn_ftp_connect = QPushButton(self.t("ftp_connect"))
        self.btn_ftp_connect.clicked.connect(self.ftp_connect)
        top_bar.addWidget(self.btn_ftp_connect)
        
        layout.addLayout(top_bar)
        
        # --- Search Bar ---
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("🔍"))
        self.ftp_local_search = QLineEdit()
        self.ftp_local_search.setPlaceholderText(self.t("ftp_search_placeholder") if "ftp_search_placeholder" in LOCALE.get(self.current_lang, {}) else "Search local...")
        self.ftp_local_search.textChanged.connect(self.ftp_filter_local)
        search_bar.addWidget(self.ftp_local_search, 1)
        
        search_bar.addWidget(QLabel("🔍"))
        self.ftp_remote_search = QLineEdit()
        self.ftp_remote_search.setPlaceholderText(self.t("ftp_search_placeholder_remote") if "ftp_search_placeholder_remote" in LOCALE.get(self.current_lang, {}) else "Search remote...")
        self.ftp_remote_search.textChanged.connect(self.ftp_filter_remote)
        self.ftp_remote_search.returnPressed.connect(self.trigger_ftp_search)
        search_bar.addWidget(self.ftp_remote_search, 1)
        
        self.chk_ftp_recursive = QCheckBox(self.t("recursive"))
        search_bar.addWidget(self.chk_ftp_recursive)
        
        layout.addLayout(search_bar)
        
        # --- Splitter (Panes) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Pane (Local)
        self.ftp_local_tree = QTreeWidget()
        self.ftp_local_tree.setHeaderLabels([self.t("ftp_name"), self.t("ftp_size"), self.t("ftp_date")])
        self.ftp_local_tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ftp_local_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Column styling (Widths & Alignment)
        # Name takes more space (+200px), Date stretches to fit
        self.ftp_local_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.ftp_local_tree.header().setStretchLastSection(False)
        self.ftp_local_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ftp_local_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Enable Multi-Select
        
        self.ftp_local_tree.setColumnWidth(0, 600) # Wider Name (was 400)
        self.ftp_local_tree.setColumnWidth(1, 80)  # Fixed Size
        
        splitter.addWidget(self.ftp_local_tree)
        self.ftp_local_tree.customContextMenuRequested.connect(self.ftp_local_context_menu)
        self.ftp_local_tree.setSortingEnabled(True)
        
        # Right Pane (Remote)
        self.ftp_remote_tree = QTreeWidget()
        self.ftp_remote_tree.setHeaderLabels([self.t("ftp_name"), self.t("ftp_size"), self.t("ftp_date")])
        self.ftp_remote_tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ftp_remote_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ftp_remote_tree.customContextMenuRequested.connect(self.ftp_remote_context_menu)
        self.ftp_remote_tree.setSortingEnabled(True)
        self.ftp_remote_tree.itemDoubleClicked.connect(self.ftp_remote_item_dbl_clicked)
        self.ftp_remote_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Enable Multi-Select
        
        # Column styling (Widths)
        self.ftp_remote_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.ftp_remote_tree.header().setStretchLastSection(False)
        self.ftp_remote_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.ftp_remote_tree.setColumnWidth(0, 700) # Wider Name (was 500)
        self.ftp_remote_tree.setColumnWidth(1, 80)  # Fixed Size

        splitter.addWidget(self.ftp_remote_tree)
        self.ftp_local_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.ftp_remote_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        layout.addWidget(splitter)

        # --- HOTKEYS ---
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        # Delete (Del)
        self.sc_del = QShortcut(QKeySequence("Del"), self.ftp_browser_page)
        self.sc_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sc_del.activated.connect(self.hotkey_delete)

        # Select All (Ctrl+A)
        self.sc_all = QShortcut(QKeySequence("Ctrl+A"), self.ftp_browser_page)
        self.sc_all.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sc_all.activated.connect(self.hotkey_select_all)
        
        # Refresh (F5)
        self.sc_refresh = QShortcut(QKeySequence("F5"), self.ftp_browser_page)
        self.sc_refresh.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sc_refresh.activated.connect(self.hotkey_refresh)

        # Copy (Ctrl+C)
        self.sc_copy = QShortcut(QKeySequence("Ctrl+C"), self.ftp_browser_page)
        self.sc_copy.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sc_copy.activated.connect(self.hotkey_copy)

        # Paste (Ctrl+V)
        self.sc_paste = QShortcut(QKeySequence("Ctrl+V"), self.ftp_browser_page)
        self.sc_paste.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sc_paste.activated.connect(self.hotkey_paste)
        
        # --- Synced Column Resizing ---
        def sync_column_width(index, old_size, new_size, source_tree, target_tree):
            target_tree.header().blockSignals(True) # Block signals to prevent recursion!
            target_tree.setColumnWidth(index, new_size)
            target_tree.header().blockSignals(False)
            
        self.ftp_local_tree.header().sectionResized.connect(
            lambda i, o, n: sync_column_width(i, o, n, self.ftp_local_tree, self.ftp_remote_tree))
        self.ftp_remote_tree.header().sectionResized.connect(
            lambda i, o, n: sync_column_width(i, o, n, self.ftp_remote_tree, self.ftp_local_tree))

        # --- Bottom Actions ---
        self.ftp_progress_bar = QProgressBar()
        self.ftp_progress_bar.setVisible(False)
        layout.addWidget(self.ftp_progress_bar)
        server_signals.ftp_progress.connect(self.ftp_progress_bar.setValue)
        server_signals.apps_scan_finished.connect(self.update_pkg_table) # Connect signal
        server_signals.ftp_progress.connect(lambda v: self.ftp_progress_bar.setVisible(v >= 0))
        
        btn_bar = QHBoxLayout()
        
        self.btn_ftp_upload = QPushButton(self.t("ftp_upload"))
        self.btn_ftp_upload.clicked.connect(self.ftp_upload_action)
        btn_bar.addWidget(self.btn_ftp_upload)
        
        self.btn_ftp_download = QPushButton(self.t("ftp_download"))
        self.btn_ftp_download.clicked.connect(self.ftp_download_action)
        btn_bar.addWidget(self.btn_ftp_download)
        
        self.btn_ftp_mkdir = QPushButton(self.t("ftp_mkdir"))
        self.btn_ftp_mkdir.clicked.connect(self.ftp_mkdir_action)
        btn_bar.addWidget(self.btn_ftp_mkdir)
        
        self.btn_ftp_delete = QPushButton(self.t("ftp_delete"))
        self.btn_ftp_delete.clicked.connect(self.ftp_delete_action)
        btn_bar.addWidget(self.btn_ftp_delete)
        
        layout.addLayout(btn_bar)
        
        # Initial load
        self.populate_drives()
        self.ftp_load_local()

        # Connect Combo Signals
        self.ftp_local_path.currentIndexChanged.connect(self.on_local_path_combo)
        self.ftp_remote_path.currentIndexChanged.connect(self.on_remote_path_combo)

        # Signals
        self.ftp_local_tree.itemDoubleClicked.connect(self.ftp_local_item_dbl_clicked)
        server_signals.ftp_connected.connect(self.on_ftp_connected)

    def populate_drives(self):
        """Populate local drives toggle."""
        self.ftp_drives.clear()
        import string
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
        self.ftp_drives.addItems(drives)
        
        # Set current drive
        current_drive = os.path.splitdrive(os.getcwd())[0] + "\\"
        index = self.ftp_drives.findText(current_drive)
        if index >= 0:
            self.ftp_drives.setCurrentIndex(index)

    def ftp_drive_changed(self, index):
        """Handle drive change."""
        drive = self.ftp_drives.currentText()
        if os.path.isdir(drive):
            self.ftp_local_path.blockSignals(True)
            self.ftp_load_local_by_path(drive) # Use helper
            self.ftp_local_path.blockSignals(False)

    def ftp_local_item_dbl_clicked(self, item, col):
        """Handle double click on local file/folder."""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isdir(path):
             self.ftp_load_local_by_path(path)

    def ftp_load_local(self):
        """Load local files into left pane from current combo text."""
        path = self.ftp_local_path.currentText()
        self.ftp_load_local_by_path(path)
        
    def ftp_load_local_by_path(self, path):
        """Helper to load path and update combo."""
        if not os.path.isdir(path): return
        
        # Update Combo (History)
        self.ftp_local_path.blockSignals(True)
        if self.ftp_local_path.findText(path) == -1:
            self.ftp_local_path.insertItem(0, path)
        self.ftp_local_path.setCurrentText(path)
        self.ftp_local_path.blockSignals(False)

        self.ftp_local_tree.clear()
        try:
            # Go up item
            parent_dir = os.path.dirname(path)
            if parent_dir and parent_dir != path:
                up_item = FTPItem(["..", "", ""])
                up_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                up_item.setData(0, Qt.ItemDataRole.UserRole, parent_dir)
                self.ftp_local_tree.addTopLevelItem(up_item)

            for f in os.listdir(path):
                if f == "." or f == "..": continue
                full = os.path.join(path, f)
                size_str = ""
                date_str = ""
                try:
                    stat = os.stat(full)
                    date_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M')
                    if os.path.isdir(full):
                        item = FTPItem([f, "", date_str])
                        item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    else:
                        size_str = f"{stat.st_size / 1024:.1f} KB"
                        if stat.st_size > 1024*1024: size_str = f"{stat.st_size / 1024 / 1024:.1f} MB"
                        item = FTPItem([f, size_str, date_str])
                        item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
                    
                    # Strictly Center Date (Col 2) for ALL items (Dir & File)
                    item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
                    
                    item.setData(0, Qt.ItemDataRole.UserRole, full)
                    self.ftp_local_tree.addTopLevelItem(item)
                except: pass
                
        except Exception as e:
            log(f"Local list error: {e}", "ERROR")

    def ftp_filter_local(self, text):
        """Filter local tree by search text."""
        for i in range(self.ftp_local_tree.topLevelItemCount()):
            item = self.ftp_local_tree.topLevelItem(i)
            if item.text(0) == "..":
                item.setHidden(False)
            else:
                item.setHidden(text.lower() not in item.text(0).lower())

    def ftp_filter_remote(self, text):
        """Filter remote tree by search text."""
        for i in range(self.ftp_remote_tree.topLevelItemCount()):
            item = self.ftp_remote_tree.topLevelItem(i)
            if item.text(0) == "..":
                item.setHidden(False)
            else:
                item.setHidden(text.lower() not in item.text(0).lower())

    def ftp_connect(self):
        """Connect to PS4 FTP."""
        ip = self.ip_input.currentText()
        if not ip:
            QMessageBox.warning(self, "Error", "IP not set")
            return
            
        if hasattr(self, 'ftp_session') and self.ftp_session:
            # Disconnect
            try:
                self.ftp_session.quit()
            except: 
                try: self.ftp_session.close()
                except: pass
            self.ftp_session = None
            server_signals.ftp_connected.emit(False)
            return

        log(f"Connecting to FTP {ip}:2121...", "INFO")
        
        # Capture UI data BEFORE thread (Main Thread)
        initial_path = self.ftp_remote_path.currentText()
        
        def connect_thread():
            try:
                ftp = ftplib.FTP()
                ftp.connect(ip, 2121, timeout=5)
                ftp.login()
                self.ftp_session = ftp
                
                # Success
                server_signals.ftp_connected.emit(True)
                
                # List initial directory
                self.ftp_list_dir(initial_path)
                
            except Exception as e:
                log(f"FTP Connection Error: {e}", "ERROR")
                self.ftp_session = None
        
        threading.Thread(target=connect_thread, daemon=True).start()

    def update_ftp_list_ui(self, files, path):
        """Update UI with FTP file list (Slot)."""
        try:
            self.ftp_remote_tree.setSortingEnabled(False)
            self.ftp_remote_tree.clear()
            
            parsed_items = []
            for line in files:
                try:
                    parts = line.split(maxsplit=8)
                    if len(parts) < 9: continue
                    perms, _, _, _, size, month, day, time_year, name = parts
                    if name == "." or name == "..": continue
                    is_dir = perms.startswith('d')
                    
                    size_str = ""
                    if not is_dir:
                        try:
                            s = int(size)
                            size_str = f"{s / 1024:.1f} KB"
                            if s > 1024*1024: size_str = f"{s / 1024 / 1024:.1f} MB"
                        except: size_str = size
                    
                    months_map = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06","Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
                    month_num = months_map.get(month, "01")
                    day_str = day.zfill(2)
                    current_year = str(datetime.datetime.now().year)
                    if ":" in time_year:
                             time_str = time_year
                             year_str = current_year
                    else:
                             time_str = "00:00"
                             year_str = time_year
                    date_str = f"{day_str}.{month_num}.{year_str} {time_str}"
                    
                    parsed_items.append({
                        "name": name,
                        "size_str": size_str,
                        "date_str": date_str,
                        "is_dir": is_dir
                    })
                except: pass
            
            # Sort: Folders first, then Files, both alphabetically by name
            parsed_items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            
            # 1. ALWAYS Add ".." if not at root
            if path != "/":
                up_item = FTPItem(["..", "", ""])
                up_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                up_item.setData(0, Qt.ItemDataRole.UserRole, "UP")
                self.ftp_remote_tree.addTopLevelItem(up_item)
            
            # 2. Add sorted folders and files
            for p in parsed_items:
                item = FTPItem([p["name"], p["size_str"], p["date_str"]])
                item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter) 
                
                if p["is_dir"]:
                    item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                else:
                    item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                    item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter) 
                
                item.setData(0, Qt.ItemDataRole.UserRole, "dir" if p["is_dir"] else "file")
                self.ftp_remote_tree.addTopLevelItem(item)
            
            self.ftp_remote_tree.setSortingEnabled(True)
            # Default sort by Name (Ascending) if no sort indicator yet or if it was cleared
            if self.ftp_remote_tree.header().sortIndicatorSection() == -1:
                self.ftp_remote_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

            self.ftp_remote_path.blockSignals(True)
            self.ftp_remote_path.setCurrentText(path)
            self.ftp_remote_path.blockSignals(False)
            
        except Exception as e:
            log(f"FTP UI Error: {e}", "ERROR")

    def ftp_list_dir(self, path):
        """List remote directory."""
        if not self.ftp_session: return
        
        def list_thread():
            try:
                self.ftp_session.cwd(path)
                files = []
                self.ftp_session.retrlines('LIST', files.append)
                self.ftp_list_signal.emit(files, path)
            except Exception as e:
                log(f"FTP List Error: {e}", "ERROR")
        
        threading.Thread(target=list_thread, daemon=True).start()

    def on_local_path_combo(self):
        """Handle local path combo change."""
        path = self.ftp_local_path.currentText()
        if os.path.isdir(path):
            self.ftp_load_local_by_path(path)
            
    def on_remote_path_combo(self):
        """Handle remote path combo change."""
        path = self.ftp_remote_path.currentText()
        # Only navigate if connected and path looks valid
        if hasattr(self, 'ftp_session') and self.ftp_session and path.startswith("/"):
             self.ftp_list_dir(path)
             
    def on_ftp_connected(self, connected):
        # Handle FTP connection signal.
        if connected:
             self.btn_ftp_connect.setText(self.t("ftp_disconnect"))
             self.btn_ftp_connect.setStyleSheet("background-color: #c0392b; color: white;")
        else:
             self.btn_ftp_connect.setText(self.t("ftp_connect"))
             self.btn_ftp_connect.setStyleSheet("")
             self.ftp_remote_tree.clear()

    def trigger_ftp_search(self):
        """Trigger search (filter or recursive)."""
        text = self.ftp_remote_search.text().strip()
        # TODO: Implement recursive search
        self.ftp_filter_remote(text)

    # --- FTP CONTEXT MENUS (MISSING IMPLEMENTATION) ---
    def ftp_local_context_menu(self, pos):
        item = self.ftp_local_tree.itemAt(pos)
        menu = QMenu()
        
        # Actions
        act_open = menu.addAction(self.t("ctx_folder")) # "Open in Folder" -> or just Open
        menu.addSeparator()
        act_rename = menu.addAction(self.t("ctx_rename"))
        act_new_folder = menu.addAction(self.t("ctx_new_folder"))
        act_delete = menu.addAction(self.t("ftp_delete"))
        menu.addSeparator()
        act_refresh = menu.addAction(self.t("ftp_refresh"))
        
        action = menu.exec(self.ftp_local_tree.viewport().mapToGlobal(pos))
        
        if action == act_open: self.ftp_local_open()
        elif action == act_rename: self.ftp_local_rename()
        elif action == act_new_folder: self.ftp_local_new_folder()
        elif action == act_delete: self.ftp_local_delete()
        elif action == act_refresh: self.ftp_load_local()

    def ftp_local_open(self):
        items = self.ftp_local_tree.selectedItems()
        if not items: return
        path = items[0].data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            if os.path.isdir(path):
                self.ftp_load_local_by_path(path)
            else:
                os.startfile(path)

    def ftp_local_rename(self):
        items = self.ftp_local_tree.selectedItems()
        if not items: return
        item = items[0]
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not old_path or item.text(0) == ".." or not os.path.exists(old_path): return
        
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, self.t("ctx_rename"), self.t("rename_wide"), text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                self.ftp_load_local()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Rename failed: {e}")

    def ftp_local_new_folder(self):
        path = self.ftp_local_path.currentText()
        if not os.path.isdir(path): return
        
        name, ok = QInputDialog.getText(self, self.t("ctx_new_folder"), self.t("ftp_mkdir") + ":")
        if ok and name:
            new_dir = os.path.join(path, name)
            try:
                os.makedirs(new_dir, exist_ok=True)
                self.ftp_load_local()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Create folder failed: {e}")

    def ftp_local_delete(self):
        items = self.ftp_local_tree.selectedItems()
        if not items: return
        path = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not path or items[0].text(0) == "..": return
        
        if QMessageBox.question(self, "Confirm", f"{self.t('ftp_delete')} '{os.path.basename(path)}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
                self.ftp_load_local()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Delete failed: {e}")

    def ftp_remote_context_menu(self, pos):
        item = self.ftp_remote_tree.itemAt(pos)
        menu = QMenu()
        
        if item:
            name = item.text(0)
            if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.dds')):
                 act_view = menu.addAction(self.t("ctx_view_img")) # "View Image"
                 action = menu.exec(self.ftp_remote_tree.viewport().mapToGlobal(pos))
                 if action == act_view: self.ftp_view_image_remote()
                 return

        # Default actions can be added here (e.g. Delete, Download)
        # For now, just View Image as requested
        # menu.exec(self.ftp_remote_tree.viewport().mapToGlobal(pos))

    def ftp_view_image_remote(self):
        items = self.ftp_remote_tree.selectedItems()
        if not items: return
        name = items[0].text(0)
        
        # Need full path?
        current_dir = self.ftp_remote_path.currentText()
        if not current_dir.endswith("/"): current_dir += "/"
        full_path = current_dir + name
        
        if not self.ftp_session: return
        
        self.lbl_sys.setText("Downloading image...")
        
        def dl_task():
            try:
                buf = io.BytesIO()
                self.ftp_session.retrbinary(f"RETR {full_path}", buf.write)
                data = buf.getvalue()
                
                # Show Dialog in Main Thread
                class ShowDlg(QObject):
                    sig = pyqtSignal()
                    def run(self): self.sig.emit()
                
                s = ShowDlg()
                s.sig.connect(lambda: ImagePreviewDialog(self, data, name).exec())
                s.run() # This runs in BG thread, emitting signal to GUI? No, unsafe. 
                
                # Correct way: pass data to signal or QTimer
                QTimer.singleShot(0, lambda: ImagePreviewDialog(self, data, name).exec())
                
            except Exception as e:
                log(f"Image DL Error: {e}", "ERROR")
            finally:
                QTimer.singleShot(0, lambda: self.lbl_sys.setText(self.t("ready")))

        threading.Thread(target=dl_task, daemon=True).start()
        if not text: return
        
        if self.chk_ftp_recursive.isChecked():
            # Start Recursive Search
            ip = self.ip_input.currentText().strip()
            if not ip: return
            
            # Check if already searching
            if hasattr(self, 'ftp_search_thread') and self.ftp_search_thread.isRunning():
                self.ftp_search_thread.stop()
                
            self.ftp_remote_tree.clear()
            self.btn_ftp_connect.setEnabled(False) # Prevent disconnect during search
            self.ftp_remote_search.setDisabled(True)
            self.ftp_progress_bar.setVisible(True)
            self.ftp_progress_bar.setRange(0, 0) # Indeterminate
            
            # Use current path if possible, else root
            cur = self.ftp_remote_path.currentText()
            if not cur or not cur.startswith("/"): cur = "/"
            
            self.ftp_search_thread = FTPSearchThread(ip, cur, text)
            self.ftp_search_thread.found_signal.connect(self.update_ftp_search_results)
            self.ftp_search_thread.finished_signal.connect(self.on_ftp_search_finished)
            self.ftp_search_thread.error_signal.connect(lambda e: log(f"FTP Search Error: {e}", "ERROR"))
            self.ftp_search_thread.start()
        else:
            # Normal Filter
            self.ftp_filter_remote(text)

    def update_ftp_search_results(self, results):
        """Add batch of results to remote tree."""
        for name, is_dir, size, date_str, full_path in results:
            item = QTreeWidgetItem(self.ftp_remote_tree)
            prefix = "📁 " if is_dir else "📄 "
            item.setText(0, f"{prefix}{name}")
            item.setText(1, size)
            item.setText(2, date_str)
            item.setData(0, Qt.ItemDataRole.UserRole, full_path) # Absolute path
            item.setData(1, Qt.ItemDataRole.UserRole, "dir" if is_dir else "file") # Type
            
            # Add tooltip with full path
            item.setToolTip(0, full_path)
            
            # Color coding for search results
            if not is_dir:
                item.setForeground(0, QBrush(QColor("#a0a0ff")))

    def on_ftp_search_finished(self):
        """Cleanup after search."""
        self.btn_ftp_connect.setEnabled(True)
        self.ftp_remote_search.setDisabled(False)
        self.ftp_progress_bar.setVisible(False)
        self.ftp_progress_bar.setRange(0, 100)
        log("FTP Recursive Search Finished", "INFO")

    def hotkey_delete(self):
        """Handle Delete key."""
        if self.ftp_local_tree.hasFocus():
            items = self.ftp_local_tree.selectedItems()
            if not items: return
            
            # Filter valid items
            valid_items = [i for i in items if i.data(0, Qt.ItemDataRole.UserRole)]
            if not valid_items: return
            
            count = len(valid_items)
            name_preview = valid_items[0].text(0)
            if count > 1: msg_text = f"{self.t('ftp_delete')} {count} items (Local)?"
            else: msg_text = f"{self.t('ftp_delete')} '{name_preview}' (Local)?"
            
            if not self.confirm_action(self.t("confirm_title"), msg_text): return
            
            for item in valid_items:
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if not path: continue
                try:
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    log(f"Deleted Local: {path}", "INFO")
                except Exception as e:
                    log(f"Local Delete Error {path}: {e}", "ERROR")
            
            self.ftp_load_local()

        elif self.ftp_remote_tree.hasFocus():
             self.ftp_delete_action()

    def hotkey_select_all(self):
        """Handle Ctrl+A."""
        if self.ftp_local_tree.hasFocus():
            self.ftp_local_tree.selectAll()
        elif self.ftp_remote_tree.hasFocus():
            self.ftp_remote_tree.selectAll()
            
    def hotkey_refresh(self):
        """Handle F5."""
        if self.ftp_local_tree.hasFocus():
            self.ftp_load_local()
        elif self.ftp_remote_tree.hasFocus():
            if self.ftp_session:
                self.ftp_list_dir(self.ftp_remote_path.currentText())

    def hotkey_copy(self):
        """Handle Ctrl+C (Copy File Name/Path)."""
        text_to_copy = ""
        if self.ftp_local_tree.hasFocus():
            items = self.ftp_local_tree.selectedItems()
            if items: text_to_copy = "\n".join([item.text(0) for item in items])
        elif self.ftp_remote_tree.hasFocus():
            items = self.ftp_remote_tree.selectedItems()
            if items: text_to_copy = "\n".join([item.text(0) for item in items])
            
        if text_to_copy:
            QApplication.clipboard().setText(text_to_copy)
            
    def hotkey_paste(self):
        """Handle Ctrl+V (Paste -> Upload/Download)."""
        if self.ftp_local_tree.hasFocus():
             self.ftp_download_action()
        elif self.ftp_remote_tree.hasFocus():
             self.ftp_upload_action()

    def confirm_action(self, title, text):
        """Helper for localized Yes/No dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        yes_txt = self.t("yes") if "yes" in LOCALE[self.current_lang] else "Yes"
        no_txt = self.t("no") if "no" in LOCALE[self.current_lang] else "No"
        btn_yes = msg.addButton(yes_txt, QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton(no_txt, QMessageBox.ButtonRole.NoRole)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.exec()
        return msg.clickedButton() == btn_yes



    def ftp_remote_item_dbl_clicked(self, item, col):
        """Handle double click on remote file/folder."""
        name = item.text(0)
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return
        
        # If data is a full path (starts with /), use it directly
        if data.startswith("/") and "/" in data[1:]:
            if item.data(1, Qt.ItemDataRole.UserRole) == "dir":
                self.ftp_list_dir(data if data.endswith("/") else data + "/")
            return

        current_path = self.ftp_remote_path.currentText()
        if not current_path.endswith("/"): current_path += "/"
        
        if data == "UP":
            # Go up
            if current_path == "/": return
            new_path = os.path.dirname(os.path.dirname(current_path)) + "/"
            self.ftp_list_dir(new_path)
            return

        if data == "dir":
             # Remove prefix from name if present
             clean_name = name.replace("📁 ", "").replace("📄 ", "")
             new_path = current_path + clean_name + "/"
             self.ftp_list_dir(new_path)

    def ftp_local_context_menu(self, pos):
        item = self.ftp_local_tree.itemAt(pos)
        menu = QMenu()
        
        if item:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and path != "UP":
                is_dir = os.path.isdir(path)
                if not is_dir:
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.ico']:
                        menu.addAction("🖼 " + (self.t("ctx_view_img") if "ctx_view_img" in LOCALE[self.current_lang] else "View Image"), 
                                     lambda: self.ftp_view_image_action(path, is_remote=False))
                
                menu.addAction("✏ " + (self.t("ctx_rename") if "ctx_rename" in LOCALE[self.current_lang] else "Rename"), 
                             lambda: self.ftp_local_rename_action(item))
                menu.addAction("🗑 " + self.t("ftp_delete"), self.hotkey_delete)
        
        menu.addSeparator()
        menu.addAction("📁 " + (self.t("ctx_new_folder") if "ctx_new_folder" in LOCALE[self.current_lang] else "New Folder"), 
                     self.ftp_local_mkdir_action)
        menu.addAction("🔄 " + self.t("pkg_refresh"), self.ftp_load_local)
        menu.exec(self.ftp_local_tree.viewport().mapToGlobal(pos))

    def ftp_remote_context_menu(self, pos):
        item = self.ftp_remote_tree.itemAt(pos)
        menu = QMenu()
        
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data != "UP":
                is_dir = item.data(1, Qt.ItemDataRole.UserRole) == "dir" if item.data(1, Qt.ItemDataRole.UserRole) else (data == "dir")
                if not is_dir:
                    name = item.text(0).replace("📁 ", "").replace("📄 ", "")
                    ext = os.path.splitext(name)[1].lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                        path = data if data.startswith("/") else os.path.join(self.ftp_remote_path.currentText(), name).replace("\\", "/")
                        menu.addAction("🖼 " + (self.t("ctx_view_img") if "ctx_view_img" in LOCALE[self.current_lang] else "View Image"), 
                                     lambda: self.ftp_view_image_action(path, is_remote=True))
                
                menu.addAction("🗑 " + self.t("ftp_delete"), self.ftp_delete_action)
        
        menu.addSeparator()
        menu.addAction("📁 " + self.t("ftp_mkdir"), self.ftp_mkdir_action)
        menu.addAction("🔄 " + self.t("pkg_refresh"), lambda: self.ftp_list_dir(self.ftp_remote_path.currentText()))
        menu.exec(self.ftp_remote_tree.viewport().mapToGlobal(pos))

    def ftp_view_image_action(self, path, is_remote=False):
        def task():
            try:
                if is_remote:
                    if not self.ftp_session: return
                    buf = io.BytesIO()
                    self.ftp_session.retrbinary(f"RETR {path}", buf.write)
                    data = buf.getvalue()
                else:
                    with open(path, "rb") as f:
                        data = f.read()
                
                if data:
                    QTimer.singleShot(0, lambda: ImagePreviewDialog(self, data, os.path.basename(path)).exec())
            except Exception as e:
                log(f"Image View Error: {e}", "ERROR")
        
        threading.Thread(target=task, daemon=True).start()

    def ftp_local_rename_action(self, item):
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not old_path or not os.path.exists(old_path): return
        
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, self.t("ctx_rename") if "ctx_rename" in LOCALE[self.current_lang] else "Rename", "New Name:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                self.ftp_load_local()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def ftp_local_mkdir_action(self):
        curr_dir = self.ftp_local_path.currentText()
        if not os.path.isdir(curr_dir): return
        
        name, ok = QInputDialog.getText(self, self.t("ctx_new_folder") if "ctx_new_folder" in LOCALE[self.current_lang] else "New Folder", "Name:")
        if ok and name:
            new_path = os.path.join(curr_dir, name)
            try:
                os.makedirs(new_path, exist_ok=True)
                self.ftp_load_local()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def ftp_mkdir_action(self):
        if not self.ftp_session: return
        name, ok = QInputDialog.getText(self, self.t("ftp_mkdir"), "Name:")
        if ok and name:
            try:
                self.ftp_session.mkd(name)
                self.ftp_list_dir(self.ftp_remote_path.currentText())
                log(f"Created folder: {name}", "INFO")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _ftp_rmtree(self, path):
        """Recursively delete a directory on FTP."""
        try:
            # List files in the directory
            files = []
            self.ftp_session.cwd(path)
            try: files = self.ftp_session.nlst()
            except: pass # Empty dir or permission error
            
            for f in files:
                if f in ['.', '..']: continue
                try:
                    # Try delete as file first
                    self.ftp_session.delete(f)
                except:
                    # If failed, assume it's a dir and recurse
                    self._ftp_rmtree(f)
            
            # Go back up and remove the now-empty dir
            self.ftp_session.rmd(path)
        except Exception as e:
            # If we acted on a file as a dir, or other error
            log(f"Recursive Delete Error ({path}): {e}", "DEBUG")
            # Ensure we are back in sync if we crashed mid-recursion?
            # It's hard to guarantee cwd is correct if we fail deep inside.
            # Best effort.

    def ftp_delete_action(self):
        if not self.ftp_session: return
        items = self.ftp_remote_tree.selectedItems()
        if not items: return
        
        valid_items = [i for i in items if i.text(0) != ".." and i.data(0, Qt.ItemDataRole.UserRole) != "UP"]
        if not valid_items: return
        
        count = len(valid_items)
        name_preview = valid_items[0].text(0)
        names_to_delete = [i.text(0) for i in valid_items]
        
        if count > 1: msg_text = f"{self.t('ftp_delete')} {count} items?"
        else: msg_text = f"{self.t('ftp_delete')} '{name_preview}'?"
        
        if not self.confirm_action(self.t("confirm_title"), msg_text): return
        
        # Run in thread to allow UI updates and prevent freezing
        def delete_thread():
            server_signals.ftp_progress.emit(0) # Show busy state
            current_path = self.ftp_remote_path.currentText()
            
            for name in names_to_delete:
                try:
                    log(f"Deleting: {name}...", "INFO")
                    try: 
                        self.ftp_session.delete(name)
                        log(f"Deleted file: {name}", "INFO")
                    except: 
                        # Try recursive delete if simple delete failed (likely a dir)
                        try:
                            self._ftp_rmtree(name)
                            log(f"Deleted folder: {name}", "INFO")
                        except Exception as e:
                             log(f"Failed to delete {name}: {e}", "ERROR")

                except Exception as e:
                    log(f"Delete Error {name}: {e}", "ERROR")
            
            server_signals.ftp_progress.emit(-1) # Hide progress
            # Refresh UI on Main Thread
            QTimer.singleShot(0, lambda: self.ftp_list_dir(current_path))

        threading.Thread(target=delete_thread, daemon=True).start()
        
        # Don't refresh immediately, wait for thread
        # self.ftp_list_dir(...)

    def ftp_upload_action(self):
        if not self.ftp_session: return
        item = self.ftp_local_tree.currentItem()
        if not item or item.text(0) == "..": return
        
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path): return
        
        def upload_thread():
            server_signals.ftp_progress.emit(0)
            try:
                if os.path.isfile(path):
                    total_size = os.path.getsize(path)
                    uploaded_bytes = 0
                    
                    def progress_callback(chunk):
                        nonlocal uploaded_bytes
                        uploaded_bytes += len(chunk)
                        if total_size > 0:
                            pct = int(uploaded_bytes / total_size * 100)
                            server_signals.ftp_progress.emit(pct)
                            
                    with open(path, 'rb') as f:
                        self.ftp_session.storbinary(f'STOR {os.path.basename(path)}', f, callback=progress_callback)
                        
                elif os.path.isdir(path):
                    # Recursive upload (no progress for now, or total size calc needed)
                    # Simple implementation for folder: just upload without fine progress per file
                    dirname = os.path.basename(path)
                    try: self.ftp_session.mkd(dirname)
                    except: pass
                    self.ftp_session.cwd(dirname)
                    for f in os.listdir(path):
                        fp = os.path.join(path, f)
                        if os.path.isfile(fp):
                            with open(fp, 'rb') as fi:
                                self.ftp_session.storbinary(f'STOR {f}', fi)
                    self.ftp_session.cwd("..")
                
                log(f"Uploaded: {os.path.basename(path)}", "INFO")
                server_signals.ftp_progress.emit(100)
                # Main thread update
                QTimer.singleShot(0, lambda: self.ftp_list_dir(self.ftp_remote_path.currentText()))
                QTimer.singleShot(2000, lambda: server_signals.ftp_progress.emit(-1))
            except Exception as e:
                log(f"Upload Error: {e}", "ERROR")
                server_signals.ftp_progress.emit(-1)
        
        threading.Thread(target=upload_thread, daemon=True).start()

    def ftp_download_action(self):
        if not self.ftp_session: return
        selected_items = self.ftp_remote_tree.selectedItems()
        if not selected_items: return
        
        # Filter out ".." item
        items_to_download = [item for item in selected_items if item.text(0) != ".."]
        if not items_to_download: return
        
        local_dir = self.ftp_local_path.currentText()
        remote_base = self.ftp_remote_path.currentText()
        
        def download_thread():
            total_files = 0
            downloaded_files = 0
            total_bytes = 0
            downloaded_bytes = 0
            
            # --- Phase 1: Calculate totals ---
            def count_remote_item(ftp, name, is_dir):
                nonlocal total_files, total_bytes
                if is_dir:
                    try:
                        ftp.cwd(name)
                        items = []
                        ftp.retrlines('LIST', items.append)
                        for line in items:
                            parts = line.split(None, 8)
                            if len(parts) < 9: continue
                            item_name = parts[8]
                            if item_name in [".", ".."]: continue
                            item_is_dir = line.startswith('d')
                            count_remote_item(ftp, item_name, item_is_dir)
                        ftp.cwd("..")
                    except Exception as e:
                        log(f"Count error in {name}: {e}", "WARN")
                else:
                    try:
                        size = ftp.size(name)
                        total_bytes += size if size else 0
                    except: pass
                    total_files += 1
            
            try:
                server_signals.ftp_progress.emit(0)
                log("Calculating download size...", "INFO")
                
                for item in items_to_download:
                    name = item.text(0)
                    is_dir = item.data(0, Qt.ItemDataRole.UserRole) == "dir"
                    count_remote_item(self.ftp_session, name, is_dir)
                
                log(f"Total: {total_files} files, {total_bytes} bytes", "INFO")
                
                # --- Phase 2: Download ---
                def download_remote_item(ftp, name, local_path, is_dir):
                    nonlocal downloaded_files, downloaded_bytes
                    
                    if is_dir:
                        os.makedirs(local_path, exist_ok=True)
                        try:
                            ftp.cwd(name)
                            items = []
                            ftp.retrlines('LIST', items.append)
                            for line in items:
                                parts = line.split(None, 8)
                                if len(parts) < 9: continue
                                item_name = parts[8]
                                if item_name in [".", ".."]: continue
                                item_is_dir = line.startswith('d')
                                download_remote_item(ftp, item_name, os.path.join(local_path, item_name), item_is_dir)
                            ftp.cwd("..")
                        except Exception as e:
                            log(f"Error downloading folder {name}: {e}", "ERROR")
                    else:
                        try:
                            with open(local_path, 'wb') as f:
                                def callback(chunk):
                                    nonlocal downloaded_bytes
                                    f.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    if total_bytes > 0:
                                        pct = int(downloaded_bytes / total_bytes * 100)
                                        server_signals.ftp_progress.emit(pct)
                                ftp.retrbinary(f'RETR {name}', callback)
                            downloaded_files += 1
                            log(f"Downloaded ({downloaded_files}/{total_files}): {name}", "INFO")
                        except Exception as e:
                            log(f"Error downloading {name}: {e}", "ERROR")
                            if os.path.exists(local_path): 
                                try: os.remove(local_path)
                                except: pass
                
                for item in items_to_download:
                    name = item.text(0)
                    is_dir = item.data(0, Qt.ItemDataRole.UserRole) == "dir"
                    download_remote_item(self.ftp_session, name, os.path.join(local_dir, name), is_dir)
                
                server_signals.ftp_progress.emit(100)
                log(f"Download complete: {downloaded_files}/{total_files} files", "INFO")
                QTimer.singleShot(1000, self.ftp_load_local)
                QTimer.singleShot(2000, lambda: server_signals.ftp_progress.emit(-1))
            except Exception as e:
                log(f"Download Error: {e}", "ERROR")
                server_signals.ftp_progress.emit(-1)
        
        threading.Thread(target=download_thread, daemon=True).start()


    def restore_widgets_after_drag(self):
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                key = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if not self.tree.itemWidget(item, 5):
                    self.setup_item_widgets(item, data[2], key)
            it += 1

    def toggle_mini_mode(self):
        self.is_mini_mode = not self.is_mini_mode
        if self.is_mini_mode:
            self.saved_geometry = self.saveGeometry()
            self.saved_col_widths = [self.tree.columnWidth(i) for i in range(10)]
            
            # Hide components
            self.sidebar.setVisible(False)
            self.top_panel_widget.setVisible(False)
            self.tree.setVisible(False)
            self.bottom_panel_widget.setVisible(False)
            if hasattr(self, 'status_frame'): self.status_frame.setVisible(False)
            
            # Button to floating
            self.btn_mini.setParent(self.central_widget)
            self.btn_mini.move(5, 5)
            self.btn_mini.show()
            self.btn_mini.setText("🔼")
            
            # Force size
            self.setFixedSize(1050, 80)
            
        else:
            # Restore components
            self.setMinimumSize(1000, 700)
            self.setMaximumSize(16777215, 16777215)
            if self.saved_geometry: self.restoreGeometry(self.saved_geometry)
            
            self.sidebar.setVisible(True)
            self.top_panel_widget.setVisible(True)
            self.tree.setVisible(True)
            self.bottom_panel_widget.setVisible(True)
            if hasattr(self, 'status_frame'): self.status_frame.setVisible(True)
            
            self.btn_mini.setParent(self.top_panel_widget)
            self.btn_mini.setText("🔽")
            
            # Re-insert into layout
            idx = self.top_layout.indexOf(self.btn_add_menu)
            if idx != -1: 
                self.top_layout.insertWidget(idx, self.btn_mini)
            else:
                self.top_layout.addWidget(self.btn_mini)
            
            # Restore columns
            if hasattr(self, 'saved_col_widths'):
                 for i, w in enumerate(self.saved_col_widths):
                     if i < 10: self.tree.setColumnWidth(i, w)

    def retranslate_ui(self):
        self.setWindowTitle(self.t("window_title"))
        self.lbl_ip.setText(self.t("ps4_ip"))
        self.btn_check.setText(self.t("check_conn"))
        self.btn_scan.setText(self.t("scan_net"))
        self.chk_overwrite.setText(self.t("overwrite"))
        self.chk_hide_pinned.setText(self.t("hide_pinned"))
        self.chk_large_font.setText(self.t("large_font"))
        self.btn_backup.setText(self.t("backup_btn"))
        self.btn_restore.setText(self.t("restore_btn"))
        self.btn_add_menu.setText(self.t("btn_add_main"))
        self.act_add_files.setText(self.t("menu_add_files"))
        self.act_add_folder.setText(self.t("menu_add_folder"))
        self.column_names = [self.t("col_file"), self.t("col_tid"), self.t("col_ver"), self.t("col_size"),
                               self.t("col_region"), self.t("col_category"),
                               self.t("col_speed"), self.t("col_prog"), self.t("col_status"), self.t("col_act")]
        self.tree.setHeaderLabels(self.column_names)
        self.btn_collapse_all.setText(self.t("collapse"))
        self.btn_expand_all.setText(self.t("expand"))
        self.btn_global_pause.setText(self.t("resume_global") if self.btn_global_pause.isChecked() else self.t("pause_global"))
        self.btn_cancel_all.setText(self.t("cancel_all"))
        self.btn_all.setText(self.t("install_all"))
        self.chk_auto_update.setText(self.t("auto_update"))
        self.lbl_sys.setText(self.t("ready"))
        self.lbl_srv.setText(self.t("server_ok").format(self.server_port_val) if self.server_status_ok else self.t("server_err"))
        
        if self.is_connected:
            self.conn_text.setStyleSheet("color: #00FF00; font-weight: bold;")
            if self.found_services.get("SPPI"): self.conn_text.setText(self.t("status_sppi_full"))
            elif self.found_services.get("RPI"): self.conn_text.setText(self.t("status_rpi_full"))
            elif self.found_services.get("FTP") and self.found_services.get("BIN"): self.conn_text.setText(self.t("status_ftp_bin"))
            elif self.found_services.get("FTP"): self.conn_text.setText(self.t("status_ftp_only"))
            elif self.found_services.get("BIN"): self.conn_text.setText(self.t("status_bin_only"))
            else: self.conn_text.setText(self.t("status_online"))
        else:
            self.conn_text.setText(self.t("status_offline")); self.conn_text.setStyleSheet("color: red; font-weight: bold;")
        self.recalc_global_stats()
        
    def save_auto_update_setting(self):
        val = self.chk_auto_update.isChecked()
        self.settings.setValue("auto_update", val)
        if val: self.check_for_updates()

    def save_column_widths(self, index, old_size, new_size):
        widths = [self.tree.columnWidth(i) for i in range(10)]
        self.settings.setValue("column_widths", ",".join(map(str, widths)))

    def switch_language(self, index):
        self.current_lang = "ru" if index == 0 else "en"
        self.settings.setValue("language", self.current_lang)
        self.retranslate_ui()

    def t(self, key): return LOCALE[self.current_lang].get(key, key)

    def on_item_collapsed(self, item): self.set_widgets_visibility_recursive(item, False)
    def on_item_expanded(self, item): self.set_widgets_visibility_recursive(item, True)
    
    def set_widgets_visibility_recursive(self, item, visible):
        for i in range(item.childCount()):
            child = item.child(i)
            for col in [7, 8, 9]:
                w = self.tree.itemWidget(child, col)
                if w: w.setVisible(visible)
            if child.childCount() > 0:
                if visible and child.isExpanded(): self.set_widgets_visibility_recursive(child, True)
                elif not visible: self.set_widgets_visibility_recursive(child, False)

    def is_item_visible_in_tree(self, item):
        parent = item.parent()
        while parent:
            if not parent.isExpanded() or parent.isHidden(): return False
            parent = parent.parent()
        return True
    def init_pkg_manager_ui(self):
        layout = QVBoxLayout(self.pkg_manager_page)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_pkg_connect = QPushButton(self.t("pkg_connect"))
        self.btn_pkg_connect.clicked.connect(self.pkg_manager_connect_toggle)
        
        # Refresh Button
        self.btn_pkg_refresh = QPushButton(self.t("pkg_refresh"))
        self.btn_pkg_refresh.clicked.connect(self.pkg_list_apps)
        
        # self.btn_pkg_uninstall = QPushButton(self.t("pkg_uninstall"))
        # self.btn_pkg_uninstall.clicked.connect(self.pkg_uninstall_app)
        # self.btn_pkg_launch = QPushButton(self.t("pkg_launch"))
        # self.btn_pkg_launch.clicked.connect(self.pkg_launch_app)
        
        toolbar.addWidget(self.btn_pkg_connect)
        toolbar.addWidget(self.btn_pkg_refresh)
        # toolbar.addWidget(self.btn_pkg_launch)
        # toolbar.addWidget(self.btn_pkg_uninstall)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Table
        self.pkg_table = QTableWidget()
        self.pkg_table.setColumnCount(5)
        self.pkg_table.setHorizontalHeaderLabels(["#", self.t("pkg_title"), self.t("pkg_tid"), self.t("pkg_ver"), self.t("pkg_size")])
        
        # FIX: Hide vertical header (duplicates # column)
        self.pkg_table.verticalHeader().setVisible(False)
        
        # FIX: Set default column widths
        self.pkg_table.setColumnWidth(0, 100) # #
        self.pkg_table.setColumnWidth(1, 500) # Name
        self.pkg_table.setColumnWidth(2, 200) # ID
        self.pkg_table.setColumnWidth(3, 200) # Ver
        self.pkg_table.setColumnWidth(4, 200) # Size

        # Alignments (Center specific columns)
        # 0=#, 2=TID, 3=Ver, 4=Size
        self.pkg_table.setItemDelegateForColumn(0, CenterDelegate(self.pkg_table))
        self.pkg_table.setItemDelegateForColumn(2, CenterDelegate(self.pkg_table))
        self.pkg_table.setItemDelegateForColumn(3, CenterDelegate(self.pkg_table))
        self.pkg_table.setItemDelegateForColumn(4, CenterDelegate(self.pkg_table))

        # Column Resizing & Saving
        self.pkg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.pkg_table.horizontalHeader().setStretchLastSection(True)
        self.pkg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.pkg_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pkg_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Load saved widths
        saved_widths = self.settings.value("pkg_table_widths", "")
        if saved_widths:
            try:
                widths = [int(w) for w in saved_widths.split(",")]
                if len(widths) == 5:
                    for i, w in enumerate(widths): self.pkg_table.setColumnWidth(i, w)
            except: pass
        else:
            self.pkg_table.setColumnWidth(0, 50)  # #
            self.pkg_table.setColumnWidth(1, 400) # Title
            self.pkg_table.setColumnWidth(2, 150) # TID
            self.pkg_table.setColumnWidth(3, 80)  # Ver
            self.pkg_table.setColumnWidth(4, 90)  # Size

        # Save on resize
        self.pkg_table.horizontalHeader().sectionResized.connect(self.save_pkg_table_columns)
        
        layout.addWidget(self.pkg_table)
    
    def init_settings_ui(self):
        layout = QVBoxLayout(self.settings_page)
        
        # Group 1: Backport Settings
        grp_backport = QGroupBox(self.t("backport_tool")); grp_backport_layout = QFormLayout(grp_backport)
        
        # Auto-detect tools path
        tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "orbis-pub-cmd.exe")
        self.backport_path = tools_path
        
        self.backport_path_edit = QLineEdit()
        self.backport_path_edit.setText(self.backport_path)
        self.backport_path_edit.setReadOnly(True) 
        self.backport_path_edit.setPlaceholderText("tools/orbis-pub-cmd.exe")
        
        # Check if exists
        exists_lbl = QLabel("✅ OK" if os.path.exists(tools_path) else "❌ " + self.t("not_found"))
        
        bp_row = QHBoxLayout()
        bp_row.addWidget(self.backport_path_edit); bp_row.addWidget(exists_lbl)
        
        grp_backport_layout.addRow("orbis-pub-cmd:", bp_row)
        
        # Checkbox: Cleanup Silent Backports
        cb_text = "Удалять папку STORM_BP_TEMP после закрытия"
        self.chk_cleanup_bp = QCheckBox(cb_text)
        self.chk_cleanup_bp.setChecked(self.settings.value("cleanup_backports", True, type=bool))
        self.chk_cleanup_bp.stateChanged.connect(lambda: self.settings.setValue("cleanup_backports", self.chk_cleanup_bp.isChecked()))
        grp_backport_layout.addRow("", self.chk_cleanup_bp)
        
        layout.addWidget(grp_backport)
        
        # Group 1.5: My List for Backport
        self.grp_my_list = QGroupBox(self.t("bp_my_list_settings"))
        ml_layout = QVBoxLayout(self.grp_my_list)
        
        # Grid of checkboxes
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(5)
        
        self.fw_checkboxes = {}
        # List from BackportDialog (must match)
        full_fw_list = [
            "5.05", "5.07", "6.50", "6.71", "6.72", "7.00", "7.02", "7.35", 
            "7.50", "7.55", "8.00", "8.52", "9.00", "9.03", "9.60", "10.00", 
            "10.71", "11.00", "11.02", "11.52", "12.00", "12.02", "12.50", 
            "12.52", "13.00", "13.02"
        ]
        
        # Load saved selection
        saved_ml = self.settings.value("backport_my_list", "5.05,6.72,9.00").split(",")
        
        cols = 8
        grid_widget.setMaximumWidth(700)
        for i, fw in enumerate(full_fw_list):
            cb = QCheckBox(fw)
            cb.setChecked(fw in saved_ml)
            cb.setStyleSheet("QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; }")
            cb.stateChanged.connect(self.save_my_list_settings)
            self.fw_checkboxes[fw] = cb
            grid.addWidget(cb, i // cols, i % cols)
            
        ml_layout.addWidget(grid_widget)
        grid.setSpacing(2)
        layout.addWidget(self.grp_my_list)
        
        # Group 2: My Firmware
        grp_my_fw = QGroupBox(self.t("my_firmware") if "my_firmware" in LOCALE[self.current_lang] else "Моя прошивка")
        fw_vbox = QVBoxLayout(grp_my_fw)
        
        fw_row = QHBoxLayout()
        cur_fw = self.settings.value("my_firmware", "---")
        self.lbl_my_fw = QLabel(f"<b>{cur_fw}</b>")
        self.lbl_my_fw.setStyleSheet("font-size: 14px; color: #05B8CC;")
        
        btn_reselect_fw = QPushButton("🔄 " + (self.t("bp_reselect") if "bp_reselect" in LOCALE[self.current_lang] else "Выбрать версию заново"))
        btn_reselect_fw.setFixedWidth(200)
        btn_reselect_fw.clicked.connect(lambda: self.check_firmware_dialog(force=True))
        
        fw_row.addWidget(QLabel(self.t("bp_fw") + " "))
        fw_row.addWidget(self.lbl_my_fw)
        fw_row.addStretch()
        fw_row.addWidget(btn_reselect_fw)
        fw_vbox.addLayout(fw_row)
        layout.addWidget(grp_my_fw)

        # Group 3: Sender Settings
        grp_sender = QGroupBox("Sender Settings" if self.current_lang == "en" else "Настройки отправителя")
        grp_sender_layout = QFormLayout(grp_sender)
        
        self.combo_concurrent = QComboBox()
        for i in range(1, 6): self.combo_concurrent.addItem(str(i))
        
        saved_concurrent = self.settings.value("max_concurrent_installs", 1, type=int)
        self.combo_concurrent.setCurrentText(str(saved_concurrent))
        self.combo_concurrent.currentTextChanged.connect(lambda v: self.settings.setValue("max_concurrent_installs", int(v)))
        
        grp_sender_layout.addRow(self.t("concurrent_installs"), self.combo_concurrent)
        layout.addWidget(grp_sender)

        # Group 4: FTP Warning Reset
        grp_ftp = QGroupBox("FTP Browser"); grp_ftp_layout = QVBoxLayout(grp_ftp)
        
        btn_reset_ftp_warn = QPushButton(self.t("reset_warn") if "reset_warn" in LOCALE[self.current_lang] else "Сбросить предупреждение")
        btn_reset_ftp_warn.clicked.connect(lambda: [
            self.settings.setValue("show_ftp_warning", True),
            self.settings.setValue("suppress_fw_dialog", False), # Reset FW Dialog suppression
            QMessageBox.information(self, "Инфо" if getattr(self, "current_lang", "en") == "ru" else "Info", 
                                    "Предупреждения сброшены." if getattr(self, "current_lang", "en") == "ru" else "Warnings reset.")
        ])
        grp_ftp_layout.addWidget(btn_reset_ftp_warn)
        
        layout.addWidget(grp_ftp)
        layout.addStretch()
        
    def save_my_list_settings(self):
        """Save selected firmwares to QSettings."""
        selected = [fw for fw, cb in self.fw_checkboxes.items() if cb.isChecked()]
        self.settings.setValue("backport_my_list", ",".join(selected))
        
    def run_backport_action(self):
        """Run Backport on selected PKG."""
        items = self.tree.selectedItems()
        if not items: return
        
        # Use auto-detected path
        bp_path = getattr(self, "backport_path", "")
        if not bp_path:
             bp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "orbis-pub-cmd.exe")
             
        if not os.path.exists(bp_path):
             QMessageBox.critical(self, self.t("backport_error"), self.t("backport_config_err") + f"\n({bp_path})")
             return

        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        pkg_path = data[2] if isinstance(data, tuple) else data
        
        if not pkg_path or not pkg_path.lower().endswith(".pkg"): return
        
        # Show Dialog
        dlg = BackportDialog(self, pkg_path)
        
        # Load last selection
        last_fw = self.settings.value("last_backport_fw", self.t("bp_all_fw"))
        idx = dlg.fw_combo.findText(last_fw)
        if idx >= 0: dlg.fw_combo.setCurrentIndex(idx)
        
        dlg.center_on_parent()
        if dlg.exec():
            selected_fw = dlg.fw_combo.currentText()
            out_dir = dlg.path_input.text()
            
            # Save for next time
            self.settings.setValue("last_backport_fw", selected_fw)
            
            # 1. Determine target firmware(s)
            target_fws = []
            if selected_fw == self.t("bp_all_fw"):
                target_fws = dlg.fw_list
            elif selected_fw == self.t("bp_my_list"):
                saved_ml = self.settings.value("backport_my_list", "").split(",")
                target_fws = [fw for fw in saved_ml if fw.strip()]
            else:
                target_fws = [selected_fw]
            
            if not target_fws:
                 QMessageBox.warning(self, "Error", "No firmware versions selected.")
                 return

            # Prepare tools once
            try:
                temp_tools = os.path.join(tempfile.gettempdir(), "storm_tools")
                os.makedirs(temp_tools, exist_ok=True)
                
                def copy_tools_from_dir(src_dir):
                    if not os.path.exists(src_dir): return
                    for fname in os.listdir(src_dir):
                        if fname.lower().endswith(".exe") or fname.lower().endswith(".dll"):
                            src_p = os.path.join(src_dir, fname)
                            dst_p = os.path.join(temp_tools, fname)
                            try:
                                shutil.copy2(src_p, dst_p)
                                if fname.lower() in ["sc.exe", "di.exe", "orbis-pub-sfo.exe"]:
                                     ext_dir = os.path.join(temp_tools, "ext")
                                     os.makedirs(ext_dir, exist_ok=True)
                                     shutil.copy2(src_p, os.path.join(ext_dir, fname))
                            except: pass

                copy_tools_from_dir(os.path.dirname(bp_path))
            except: pass

            tool_paths = {
                "cmd": os.path.join(temp_tools, "orbis-pub-cmd.exe"), 
                "sfo": os.path.join(temp_tools, "orbis-pub-sfo.exe")
            }
            
            self.lbl_sys.setText("Backporting...")
            threading.Thread(target=self._execute_backport_all, args=(pkg_path, out_dir, target_fws, tool_paths), daemon=True).start()


    def save_pkg_table_columns(self, index, old, new):
        widths = [self.pkg_table.columnWidth(i) for i in range(5)]
        self.settings.setValue("pkg_table_widths", ",".join(map(str, widths)))

    def pkg_manager_connect_toggle(self):
        """Toggle connection to PKG Manager (Connect/Disconnect)."""
        if self.btn_pkg_connect.text() == self.t("ftp_disconnect"):
            # Disconnect
            self.pkg_table.setRowCount(0)
            self.btn_pkg_connect.setText(self.t("pkg_connect"))
            log("PKG Manager Disconnected", "INFO")
            return
            
        # Connect logic
        self.pkg_list_apps()

    def pkg_list_apps(self):
        ip = self.ip_input.currentText()
        if not ip: 
            QMessageBox.warning(self, "IP Error", "IP is empty")
            return
        
        def list_thread():
            apps_list = []
            try:
                log(f"PKG Manager: Connecting to FTP {ip}:2121...", "INFO")
                ftp = ftplib.FTP()
                # FIX: Timeout 15s to avoid early timeout on slow PS4
                ftp.connect(ip, 2121, timeout=15) 
                ftp.login()
                ftp.set_pasv(True) # Explicit PASV
                ftp.voidcmd('TYPE I')
                
                app_dirs = []
                check_paths = ["/user/app/", "/user/appmeta/"]
                
                success_path = ""
                for path in check_paths:
                    try:
                        ftp.cwd(path)
                        app_dirs = ftp.nlst()
                        success_path = path
                        break
                    except Exception as e:
                        log(f"PKG Manager: Failed access {path}: {e}", "WARN")
                
                if not success_path:
                    # Retry once with Active mode if PASV failed
                    try:
                        log("PKG Manager: Retrying with Active Mode...", "INFO")
                        ftp.set_pasv(False)
                        ftp.cwd("/user/app/")
                        app_dirs = ftp.nlst()
                        success_path = "/user/app/"
                    except Exception as e:
                        log(f"PKG Manager: Critical access error: {e}", "ERROR")
                        QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", f"Cannot access /user/app/ (Timeout/Perms)\n{e}"))
                        return

                log(f"PKG Manager: Found {len(app_dirs)} app directories in {success_path}", "INFO")
                
                for title_id in app_dirs:
                    if title_id in [".", ".."]: continue
                    
                    app_name = title_id
                    app_ver = "00.00"
                    total_size = 0
                    
                    # Try to read param.sfo for real name and version
                    sfo_candidates = [
                         f"{success_path}/{title_id}/sce_sys/param.sfo",
                         f"/user/appmeta/{title_id}/param.sfo",
                         f"/system_data/priv/app/{title_id}/sce_sys/param.sfo"
                    ]
                    
                    # Fix path double slashes just in case
                    sfo_candidates = [p.replace("//", "/") for p in sfo_candidates]
                    
                    found_sfo = False
                    for sfo_path in sfo_candidates:
                        try:
                            buf = io.BytesIO()
                            ftp.retrbinary(f"RETR {sfo_path}", buf.write)
                            data = buf.getvalue()
                            if len(data) > 0:
                                info = get_pkg_info_from_sfo(data)
                                if info.get("TITLE"):
                                    app_name = info["TITLE"]
                                    found_sfo = True
                                if info.get("APP_VER"):
                                    app_ver = info["APP_VER"]
                                elif info.get("VERSION"):
                                    app_ver = info["VERSION"]
                                break
                        except: continue

                    # Calculate size (Simplified: look at main directory)
                    try:
                        # Use success path for size check if possible
                        target_dir = f"{success_path}/{title_id}".replace("//", "/")
                        ftp.cwd(target_dir)
                        items = []
                        ftp.retrlines('LIST', items.append)
                        for item in items:
                            parts = item.split(maxsplit=8)
                            if len(parts) >= 9:
                                size = parts[4]
                                if not item.startswith('d'):
                                    try: total_size += int(size)
                                    except: pass
                    except: pass
                    
                    size_str = f"{total_size / 1024 / 1024:.1f} MB" if total_size > 0 else "---"
                    
                    apps_list.append({
                        "title_id": title_id,
                        "name": app_name,
                        "ver": app_ver,
                        "size": size_str
                    })
                
                # Sort apps by name by default
                apps_list.sort(key=lambda x: x['name'].lower())
                
                ftp.quit()
                log(f"PKG Manager: Loaded {len(apps_list)} apps", "INFO")
                
                if apps_list:
                    server_signals.apps_scan_finished.emit(apps_list)
                    QTimer.singleShot(0, lambda: self.btn_pkg_connect.setText(self.t("ftp_disconnect")))
                else:
                    log("PKG Manager: No apps found", "WARN")
                    QTimer.singleShot(0, lambda: QMessageBox.information(self, "Info", "No apps found in /user/app/"))
                    
            except Exception as e:
                log(f"PKG Manager Error: {e}", "ERROR")
                err_msg = str(e)
                if "Connection refused" in err_msg or "10061" in err_msg:
                    advice = "FTP Connection Refused.\n\nMake sure GoldHEN FTP is running on PS4 (port 2121)."
                    if self.current_lang == "ru":
                        advice = "FTP: Подключение отклонено.\n\nУбедитесь, что GoldHEN FTP запущен на PS4 (порт 2121)."
                else:
                    advice = f"Exception: {e}"
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", advice))
        
        threading.Thread(target=list_thread, daemon=True).start()

    def update_pkg_table(self, apps):
        try:
            log(f"DEBUG: update_pkg_table called with {type(apps)}", "DEBUG")
            if isinstance(apps, list) and len(apps) > 0:
                 log(f"DEBUG: First item type: {type(apps[0])} -> {str(apps[0])[:100]}...", "DEBUG")

            self.pkg_table.setRowCount(0)
            
            # FIX: Robust Dict handling
            if isinstance(apps, dict):
                # If wrapped in "apps" key
                if "apps" in apps and isinstance(apps["apps"], list):
                    apps = apps["apps"]
                else:
                    # Convert { "CUSA": "Name" } OR { "CUSA": { ... } } to List
                    new_list = []
                    for k, v in apps.items():
                        item = {}
                        if isinstance(v, dict):
                            item = v.copy()
                            if "title_id" not in item: item["title_id"] = k
                        else:
                            # Assume value is the Name
                            item = {"title_id": k, "name": str(v)}
                        new_list.append(item)
                    
                    apps = new_list
                    log(f"DEBUG: Normalized apps dict to {len(apps)} items.", "INFO")

            if not apps:
                QMessageBox.warning(self, self.t("pkg_manager"), self.t("pkg_not_found") + "\n\n(No apps returned from PS4. Check if GoldHEN/RPI is running properly.)")
                return

            for app in apps:
                # Ensure app is dict
                if not isinstance(app, dict):
                    log(f"Skipping invalid app data types: {app}", "DEBUG")
                    continue
                    
                row = self.pkg_table.rowCount()
                self.pkg_table.insertRow(row)
                
                # Helper to get value case-insensitively or by known variants
                def get_val(d, keys, default=""):
                    for k in keys:
                        if k in d: return str(d[k])
                    # Try lowercase keys
                    lower_keys = {k.lower(): v for k, v in d.items()}
                    for k in keys:
                        if k.lower() in lower_keys: return str(lower_keys[k.lower()])
                    return default

                name = get_val(app, ["title_name", "TitleName", "name", "desc"], "Unknown")
                tid = get_val(app, ["title_id", "TitleId", "id", "npTitleId"], "")
                ver = get_val(app, ["version", "Version", "app_ver", "ver"], "")
                size = get_val(app, ["size", "Size", "file_size", "totalSize"], "")

                self.pkg_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self.pkg_table.setItem(row, 1, QTableWidgetItem(name))
                self.pkg_table.setItem(row, 2, QTableWidgetItem(tid))
                self.pkg_table.setItem(row, 3, QTableWidgetItem(ver))
                self.pkg_table.setItem(row, 4, QTableWidgetItem(size))
        except Exception as e:
            log(f"Table Update Error: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to update table: {e}")

    def pkg_uninstall_app(self):
        items = self.pkg_table.selectedItems()
        if not items: return
        row = items[0].row()
        tid = self.pkg_table.item(row, 2).text()
        name = self.pkg_table.item(row, 1).text()
        
        title = self.t("confirm_uninstall")
        msg = self.t("msg_confirm_uninstall").format(name, tid)
        if not self.confirm_action(title, msg): return
        
        ip = self.ip_input.currentText()
        def task():
            ports = [12800, 12813, 12801]
            success = False
            for port in ports:
                try:
                    url = f"http://{ip}:{port}/api/uninstall"
                    log(f"Trying uninstall on port {port}...", "DEBUG")
                    requests.post(url, json={"title_id": tid}, timeout=5)
                    log(f"Uninstall command sent to {port} for {tid}", "INFO")
                    success = True
                    break
                except: pass
            
            if not success:
                log(f"Uninstall failed: No RPI/SPPI service found on ports {ports}", "ERROR")
            else:
                time.sleep(2)
                QTimer.singleShot(0, self.pkg_list_apps)
        threading.Thread(target=task, daemon=True).start()

    def pkg_launch_app(self):
        items = self.pkg_table.selectedItems()
        if not items: return
        row = items[0].row()
        tid = self.pkg_table.item(row, 2).text()
        
        ip = self.ip_input.currentText()
        def task():
            ports = [12800, 12813, 12801]
            success = False
            for port in ports:
                try:
                    url = f"http://{ip}:{port}/api/launch"
                    log(f"Trying launch on port {port}...", "DEBUG")
                    requests.post(url, json={"title_id": tid}, timeout=5)
                    log(f"Launch command sent to {port} for {tid}", "INFO")
                    success = True
                    break
                except: pass
            
            if not success:
                log(f"Launch failed: No RPI/SPPI service found on ports {ports}", "ERROR")
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, self.t("error"), self.t("status_offline") + " (RPI)"))

        threading.Thread(target=task, daemon=True).start()

    def start_startup_sequence(self):
        self.start_server()
        self.load_pinned_data()
        self.init_backup_thread()
        if self.pinned_folders:
            self.lbl_sys.setText("⏳ ...")
            # Participate in active_loaders to prevent premature cleanup
            self.active_loaders += 1
            theme = THEMES.get(self.theme_combo.currentText(), THEMES["Dark (Default)"])
            self.loader_thread = LoaderThread(self.pinned_folders, is_startup=True, theme_type=theme["type"], mode="folder", batch_size=20)
            self.loader_thread.start()
        self.scan_network()
        
    def init_backup_thread(self):
        ip = self.settings.value("ps4_ip", "")
        path = self.settings.value("backup_path", "")
        interval = int(self.settings.value("backup_interval", 60))
        enabled = self.settings.value("backup_enabled", False, type=bool)
        self.backup_thread = BackupThread(ip, self.rpi_port, path, interval, enabled)
        self.backup_thread.start()

    def open_backup_settings(self):
        dlg = BackupDialog(self, self.settings); dlg.setStyleSheet(self.styleSheet())
        if dlg.exec():
            ip = self.ip_input.currentText()
            path = self.settings.value("backup_path", "")
            interval = int(self.settings.value("backup_interval", 60))
            enabled = self.settings.value("backup_enabled", False, type=bool)
            if self.backup_thread:
                self.backup_thread.update_settings(ip, path, interval, enabled)
                if dlg.should_force: self.backup_thread.trigger_backup()

    def on_backup_started(self):
        self.btn_backup.setText("⏳")
        self.btn_backup.setStyleSheet("background-color: #d35400; color: white; border: 1px solid #a04000; padding: 6px; font-weight: bold;")
        self.btn_backup.setEnabled(False)

    def on_backup_finished(self):
        self.btn_backup.setText(self.t("backup_btn")); self.btn_backup.setStyleSheet(""); self.btn_backup.setEnabled(True)

    def open_restore_dialog(self):
        ip = self.ip_input.currentText()
        if not ip: QMessageBox.warning(self, self.t("error"), "IP required"); return
        dlg = RestoreDialog(self, ip, self.settings); dlg.setStyleSheet(self.styleSheet())
        if dlg.exec():
            items = dlg.selected_items_to_restore
            if items:
                self.restore_thread = RestoreThread(ip, items)
                self.restore_thread.start()
                self.btn_restore.setEnabled(False); self.btn_restore.setText("⏳")

    def on_restore_finished(self):
        self.btn_restore.setEnabled(True); self.btn_restore.setText(self.t("restore_btn"))
        QMessageBox.information(self, self.t("done"), self.t("rest_success"))

    def scan_network(self):
        self.lbl_sys.setText(self.t("scan_start"))
        self.scan_thread = ScanThread()
        self.scan_thread.start()

    def on_scan_finished(self, results):
        self.ip_input.clear()
        if results:
            found_first = results[0]
            for ip, port in results: self.ip_input.addItem(ip)
            self.ip_input.setCurrentText(found_first[0])
            self.ping_ps4() 
        else:
            self.lbl_sys.setText(self.t("scan_fail"))
            if self.ip_input.currentText(): self.ping_ps4()

    def check_for_updates(self):
        self.lbl_sys.setText("⏳ Checking updates...")
        self.update_checker = UpdateCheckerThread()
        self.update_checker.start()

    def on_update_found(self, ver, url):
        self.lbl_sys.setText(self.t("ready"))
        dlg = UpdateDialog(self, ver, url, self.current_lang)
        dlg.setStyleSheet(self.styleSheet())
        dlg.exec()

    def on_update_not_found(self): self.lbl_sys.setText(self.t("upd_no_new"))

    def toggle_mini_mode(self):
        self.is_mini_mode = not self.is_mini_mode
        if self.is_mini_mode:
            # Save State
            self.saved_geometry = self.saveGeometry()
            
            # Hide components
            self.sidebar.setVisible(False)
            self.tree.setVisible(False)
            self.bottom_panel_widget.setVisible(False)
            self.status_frame.setVisible(False)
            if hasattr(self, 'top_panel_widget'): self.top_panel_widget.setVisible(False)
            
            # Force size for Mini Mode
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedSize(800, 80)
            
            # Change toggle button text
            self.btn_mini.setText("🔼")
            
        else:
            # Restore Normal Mode
            self.setMinimumSize(1000, 700)
            self.setMaximumSize(16777215, 16777215)
            if self.saved_geometry:
                self.restoreGeometry(self.saved_geometry)
            
            # Restore components
            self.sidebar.setVisible(True)
            self.tree.setVisible(True)
            self.bottom_panel_widget.setVisible(True)
            self.status_frame.setVisible(True)
            if hasattr(self, 'top_panel_widget'): self.top_panel_widget.setVisible(True)
            
            # Change toggle button text
            self.btn_mini.setText("🔽")

    def force_taskbar_icon(self):
        try:
            icon_path = resource_path("stormps4pkgsender.ico")
            if not os.path.exists(icon_path): return
            hwnd = int(self.winId())
            h_icon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010 | 0x00008000) 
            if h_icon:
                ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, h_icon)
                ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, h_icon)
        except: pass

    # --- PING & CONNECTION LOGIC ---
    def ping_ps4(self):
        ip = self.ip_input.currentText().strip()
        if not ip: return
        self.is_pinging = True
        self.lbl_sys.setText(self.t("checking"))
        self.conn_dot.setStyleSheet("color: orange; font-size: 18px;")
        self.conn_text.setText(self.t("checking")); self.conn_text.setStyleSheet("color: orange; font-weight: bold;")
        if self.backup_thread: self.backup_thread.ip = ip
        
        def check_all_ports():
            status = {"RPI": False, "RPI_OOP": False, "SPPI": False, "FTP": False, "BIN": False}
            try:
                # SPPI (12813)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2.0)
                    s.connect((ip, 12813))
                    status["SPPI"] = True
                    self.rpi_port = 12813
                    s.close()
                    log("SPPI (12813) = Connected", "INFO")
                except Exception:
                    log("SPPI (12813) = Failed", "DEBUG")

                # RPI OOP (12801)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2.0)
                    s.connect((ip, 12801))
                    status["RPI_OOP"] = True
                    if not status["SPPI"]: self.rpi_port = 12801
                    s.close()
                    log("RPI OOP (12801) = Connected", "INFO")
                except Exception:
                    log("RPI OOP (12801) = Failed", "DEBUG")

                # RPI FlatZ (12800)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2.0)
                    s.connect((ip, 12800))
                    status["RPI"] = True
                    if not status["SPPI"] and not status["RPI_OOP"]: self.rpi_port = 12800
                    s.close()
                    log("RPI FlatZ (12800) = Connected", "INFO")
                except Exception:
                    log("RPI FlatZ (12800) = Failed", "DEBUG")

                # FTP (2121)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(3.0)
                    s.connect((ip, 2121))
                    status["FTP"] = True
                    log("FTP (2121) = Connected", "INFO")
                    s.close()
                except: log("FTP (2121) = Failed", "DEBUG")

                # BinLoader (9090)
                for i in range(3):
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2.0)
                        s.connect((ip, 9090))
                        status["BIN"] = True
                        s.close()
                        log("BinLoader (9090) = Connected", "INFO")
                        break
                    except Exception as e:
                        if i == 2: log(f"BinLoader (9090) = Failed: {e}", "DEBUG")
                        time.sleep(0.5)
                
            except Exception as e:
                log(f"Ping Error: {e}", "ERROR")



            server_signals.ping_result.emit(status)
        threading.Thread(target=check_all_ports, daemon=True).start()

    def handle_ping_result(self, status):
        self.is_pinging = False
        self.found_services = status
        is_online = any(status.values())
        self.is_connected = is_online
        
        if is_online:
            self.conn_dot.setStyleSheet("color: #00FF00; font-size: 18px;")
            self.conn_text.setStyleSheet("color: #00FF00; font-weight: bold;")
            
            # Build list of ALL connected services
            active_services = []
            if status.get("SPPI"): 
                active_services.append("SPPI")
                self.rpi_port = 12813
            if status.get("RPI"): 
                active_services.append("RPI")
                if not status.get("SPPI"):  # Only set if SPPI not available
                    self.rpi_port = 12800
            if status.get("FTP"): active_services.append("FTP")
            if status.get("BIN"): active_services.append("BIN")
            
            # Display combined status
            if active_services:
                service_str = ", ".join(active_services)
                if self.current_lang == "ru":
                    self.conn_text.setText(f"В сети ({service_str})")
                else:
                    self.conn_text.setText(f"Online ({service_str})")
            else:
                self.conn_text.setText(self.t("status_online"))
            
            self.lbl_sys.setText(self.t("ready"))
        else:
            self.conn_dot.setStyleSheet("color: red; font-size: 18px;")
            self.conn_text.setText(self.t("status_offline"))
            self.conn_text.setStyleSheet("color: red; font-weight: bold;")
            self.lbl_sys.setText(self.t("scan_fail"))

        if is_online and self.install_queue and not self.is_processing_queue: self.process_next_in_queue()

    # --- INSTALLATION LOGIC (RESTORED FROM v1.1.7) ---
    # --- INSTALLATION LOGIC (RESTORED FROM v1.1.7) ---
    def process_next_in_queue(self):
        """Start next item(s) from queue based on concurrent limit, respecting Theme dependencies."""
        self.is_processing_queue = True
        if self.is_global_paused: return
        if not self.install_queue: return
        
        limit = self.settings.value("max_concurrent_installs", 1, type=int)
        
        # Iterate to find eligible items (not blocked by dependency)
        # We cannot just pop(0) blindly.
        i = 0
        while len(self.active_installs) < limit and i < len(self.install_queue):
            item = self.install_queue[i]
            
            # --- DEPENDENCY CHECK ---
            if self.is_theme_blocked(item):
                i += 1 # Skip this item, look at next
                continue
            
            # Start this item
            self.install_queue.pop(i) # Remove specific item
            self.active_installs.append(item)
            
            # Use small delay to prevent rapid UI spam on multiple starts
            # FIX: Increased delay to 1.5s to prevent overwhelming SPPI with multiple concurrent requests
            QTimer.singleShot(1500, lambda it=item: self.run_install(it))
            # Do NOT increment i, because next item shifted to position i

    def is_theme_blocked(self, item):
        """Check if Theme Part 2 is blocked by Part 1."""
        try:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data: return False
            fname = data[0] if isinstance(data, tuple) else data
            
            # Check if name indicates Part 2
            # Patterns: "Name_2.pkg" or ending in "_2.pkg" (case insensitive)
            if "_2." in fname.lower() and fname.lower().endswith(".pkg"):
                # Construct target Part 1 name
                target_1 = fname.replace("_2.", "_1.").replace("_2.PKG", "_1.PKG").replace("_2.pkg", "_1.pkg")
                
                # Check Active Installs
                for act in self.active_installs:
                    d_act = act.data(0, Qt.ItemDataRole.UserRole)
                    if not d_act: continue
                    n_act = d_act[0] if isinstance(d_act, tuple) else d_act
                    if n_act == target_1:
                        log(f" Dependency Block: {fname} waiting for {target_1} (Active)", "INFO")
                        return True
                
                # Check Queue (if Part 1 is still waiting in queue)
                # Note: If it's in queue, it might be BEFORE or AFTER current item?
                # Usually BEFORE, because we sort. 
                # If it's AFTER, then we shouldn't block? No, if it's anywhere not DONE, we wait.
                # Actually, simpler: Is Part 1 is in Queue?
                for q_item in self.install_queue:
                    if q_item == item: continue # Skip self
                    d_q = q_item.data(0, Qt.ItemDataRole.UserRole)
                    if not d_q: continue
                    n_q = d_q[0] if isinstance(d_q, tuple) else d_q
                    if n_q == target_1:
                        log(f" Dependency Block: {fname} waiting for {target_1} (Queued)", "INFO")
                        return True
                        
                # If not active and not queued, assume Done or Missing -> Allow
                return False
        except: 
            return False
            
        return False

    def run_install(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: self.finish_item_processing(item); return
        
        fname = data
        tid = ""
        fpath = data
        if isinstance(data, tuple):
             fname, tid, fpath = data
        
        key = item.data(0, Qt.ItemDataRole.UserRole + 1)
        
        # --- AUTO-BACKPORT CHECK ---
        temp_backport_pkg = None
        try:
            f_size = os.path.getsize(fpath)
            # If < 1MB (1048576 bytes) and My Firmware set
            my_fw = self.settings.value("my_firmware", "")
            
            # DIAGNOSTIC LOGGING
            log(f"Auto-Backport Check: Size={f_size}, FW={my_fw}, Limit=1MB", "DEBUG")
            
            # CUSTOM LOGIC: Exclude Themes from Auto-Backport
            is_theme_cat = "THEME" in item.text(5).upper()
            
            if f_size < 1048576 and my_fw and not is_theme_cat:
                 log(f"Auto-Backport triggered for small file: {fname} (FW: {my_fw})", "INFO")
                 server_signals.install_status.emit(str(key), "CHECKING", "Backporting...")
                 
                 # Run synchronously (UI might freeze slightly but for <1MB it's fast)
                 # Or use QThread if blocking is an issue. 
                 # For <1MB, unpacking and repacking is < 1-2 seconds.
                 bp_pkg = self.silent_backport(fpath, my_fw)
                 
                 if bp_pkg and os.path.exists(bp_pkg):
                     fpath = bp_pkg # SWAP FILE
                     log(f"Using backport: {bp_pkg}", "INFO")
                     temp_backport_pkg = bp_pkg
                     self.temp_backports[key] = bp_pkg # Mark for cleanup
                     
                     # CRITICAL: Update server map so it serves the NEW file
                     self.file_map[str(key)] = bp_pkg
                     self.file_sizes_map[str(key)] = os.path.getsize(bp_pkg)
                     
                     # UPDATE UI ITEM
                     # item.setData(0, Qt.ItemDataRole.UserRole, (fname, tid, fpath)) # keep original name?
                     # Better keep original name in UI but use new path
                     item.setData(0, Qt.ItemDataRole.UserRole, (fname, tid, fpath))
                     item.setText(3, format_size(os.path.getsize(fpath)))
                     if not item.text(0).startswith("✅ BP:"):
                          item.setText(0, "✅ BP: " + item.text(0).replace("📄 ", "").replace("  ┗ ", ""))
                 else:
                     log("Auto-Backport failed. Using original.", "WARN")
            elif is_theme_cat and f_size < 1048576:
                 log(f"Auto-Backport skipped for Theme: {fname}", "INFO")
        except Exception as e:
            log(f"Auto-Backport Error: {e}", "ERROR")

        file_ver = "01.00"
        try: _, file_ver = parse_pkg_info(fpath)
        except: pass
        if tid: tid = tid.upper().strip()
        
        if not self.chk_overwrite.isChecked() and tid in self.installed_apps_cache:
            installed_ver = self.installed_apps_cache[tid]
            try:
                if float(file_ver) <= float(installed_ver):
                    server_signals.install_status.emit(str(key), "ALREADY", "")
                    return
            except: 
                server_signals.install_status.emit(str(key), "ALREADY", "")
                return

        set_file_state(str(key), "RUNNING")   
        st = self.tree.itemWidget(item, 8)
        btn_widget = self.tree.itemWidget(item, 9)
        
        if st:
            txt = st.text().lower()
            is_done = "already" in txt or "done" in txt or "installed" in txt or "установлено" in txt or "завершено" in txt or "ранее" in txt
            if is_done and not self.chk_overwrite.isChecked():
                self.finish_item_processing(item); return
            
            if btn_widget:
                if is_done: btn_widget.setVisible(False)
                elif self.is_item_visible_in_tree(item): btn_widget.setVisible(True)
        
        if not os.path.exists(fpath): self.finish_item_processing(item); return
        
        # ВАЖНО: Картируем и по имени, и по ключу.
        self.file_map[fname] = fpath
        if key: self.file_map[str(key)] = fpath
        PS4HTTPHandler.map_files = self.file_map
        
        self.handle_install_status(key, "CHECKING", "")
        
        ip = self.ip_input.currentText().strip()
        port = self.port_input.text().strip()

        def wrk():
            try:
                
                # Определение локального IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.connect((ip, 1))  # Подключаемся к PS4 IP для правильного определения интерфейса
                    loc = s.getsockname()[0]
                except:
                    loc = "127.0.0.1"
                finally:
                    s.close()
                
                # --- FIX: URL with Real Filename ---
                # SPPI relies on the filename in the URL to determine file type (e.g. for Themes).
                # We sanitize the filename to be URL-safe but keep the extension.
                
                safe_name = urllib.parse.quote(fname)
                # Ensure it ends with .pkg
                if not safe_name.lower().endswith('.pkg'): safe_name += ".pkg"
                
                # We still need the key for our internal map lookup. 
                # Strategy: path = /<key>/<safe_name>  OR  path = /<safe_name>?key=<key>
                # Let's try simple path: /<safe_name> and rely on map lookup by NAME first?
                # No, name might not be unique.
                # Let's use: /<key>/<safe_name> -> Handler must handle this.
                # OR easier: /<key>.pkg?name=<safe_name> -> PS4 ignores query params?
                # Best for SPPI: Just the filename. 
                # We map NAME -> PATH in on_loader_file logic (self.file_map[name] = full_path).
                # BUT duplicate names exist.
                # 
                # Let's use the KEY in the filename? e.g. "MyTheme_12345.pkg" -> might break detection if it expects specific pattern?
                # 
                # Let's try: URL = /<key>/<safe_name> 
                # Handler logic: split('/')[1] is key.
                
                # Actually, simplest check: SPPI might just need the extension and cleaner name.
                # The issue reported: "FILES THEME ... defined as GAME, no TitleID".
                # This means it parsed the PKG header? Or failed and defaulted to Game?
                # If Error -0x1, it failed BEFORE installing usually.
                
                # Let's try serving with specific sanitized name.
                # We will register a temporary alias in file_map if needed, or just use the existing key map.
                # Let's construct URL: http://ip:port/<safe_name>
                # And ensure file_map has <safe_name> -> fpath
                
                # Sanitize name deeply
                clean_name = re.sub(r'[^\w\-. ]', '_', fname)
                while "__" in clean_name: clean_name = clean_name.replace("__", "_")
                quoted_name = urllib.parse.quote(clean_name)
                
                # Register map
                self.file_map[clean_name] = fpath
                PS4HTTPHandler.map_files = self.file_map
                
                # FIX: Progress Bar Mapping (Name -> Hash)
                # Ensure Handler knows that 'clean_name' actually corresponds to 'key' (the hash)
                if key:
                     PS4HTTPHandler.file_key_map[clean_name] = str(key)
                
                p_url = f"http://{loc}:{port}/{quoted_name}"
                
                # Debug: показываем URL для диагностики
                print(f"[DEBUG] Sending to PS4: {p_url}")  
                print(f"[DEBUG] Local IP: {loc}, Server Port: {port}")
                
                server_signals.install_status.emit(key, "START", "")
                
                max_retries = 10  # Increased from 5 to give PS4 more time after previous install
                active_port = self.rpi_port
                
                for attempt in range(max_retries):
                    port_ok = False
                    # User Requested Order: 12813 (SPPI) -> 12801 -> 12800 (RPI)
                    final_checks = [12813, 12801, 12800]

                    for p_check in final_checks:
                        try:
                            ts = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            ts.settimeout(1.0)
                            result = ts.connect_ex((ip, p_check))
                            ts.close()
                            if result == 0:
                                active_port = p_check
                                port_ok = True
                                log(f"Port {p_check} available", "INFO")
                                break
                        except Exception as e:
                            log(f"Port check error {p_check}: {e}", "WARN")
                    
                    if not port_ok:
                        if attempt < max_retries - 1:
                            server_signals.install_status.emit(key, "CHECKING", f"Wait PS4 ({attempt+1})...")
                            time.sleep(2.5)
                            continue
                        else:
                            server_signals.install_status.emit(key, "ERROR", self.t("timeout"))
                            return

                    # --- FIX: ROBUST INSTALL LOGIC ---
                    url = f"http://{ip}:{active_port}/api/install"
                    try:
                        headers = {'Connection': 'close'}
                        # FIX: SPPI (12813) expects URL directly, RPI (12800/12801) expects packages array
                        f_size = self.file_sizes_map.get(str(key), 0)
                        if active_port == 12813:
                            payload = {"url": p_url, "file_size": f_size}
                        else:
                            payload = {"type": "direct", "packages": [p_url]}
                        
                        log(f"Sending to port {active_port}: {payload}", "DEBUG")
                        
                        r = None # FIX: Initialize r to prevent UnboundLocalError
                        # FIX: Retry Logic (Re-applied) with 30s Timeout
                        for install_attempt in range(3):
                            try:
                                r = self.http_session.post(url, json=payload, headers=headers, timeout=30)
                                break # Success
                            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, Exception) as net_err:
                                # FIX: Smart Duplicate Prevention
                                # If download started while we were waiting/failing, STOP RETRYING!
                                if key in self.progress_map and self.progress_map.get(key, 0) > 0:
                                     log(f"Retry aborted: Download already active for {key}", "INFO")
                                     break

                                if install_attempt == 2: raise net_err # Re-raise on last fail
                                log(f"API Retry ({install_attempt+1}): {net_err}", "WARN")
                                time.sleep(1.0)
                        
                        status_code = r.status_code if r else "None"
                        log(f"API: {url} -> {status_code}", "DEBUG")
                        
                        if r and r.status_code == 200:
                            try:
                                # FIX: SPPI sends invalid JSON with HEX ints (0xFFFFFFFE)
                                # We must sanitize it before parsing
                                raw_json = r.text
                                # Replace Hex numbers with Integers (decimal)
                                # Matches 0x followed by hex digits, capturing them to convert
                                clean_json = re.sub(r'0x([0-9a-fA-F]+)', lambda m: str(int(m.group(0), 16)), raw_json)
                                
                                resp = json.loads(clean_json)
                                
                                if resp.get("success", False) == True:
                                    log(f"API Success for {key}. Task accepted.", "INFO")
                                    server_signals.install_status.emit(key, "QUEUE", "")
                                    
                                    # CLEANUP TEMP BACKPORT
                                    if temp_backport_pkg and os.path.exists(temp_backport_pkg):
                                        try:
                                            # We generally wait until install is DONE. 
                                            # But if we delete now, PS4 might fail if it uses direct link?
                                            # NO, we use type="direct" with URL. 
                                            # If logic is "direct", the PS4 downloads from OUR server (http://loc:port/key.pkg).
                                            # So we CANNOT delete it yet! 
                                            # We must keep it until the transfer is complete.
                                            
                                            # Store in a list to delete later?
                                            # Or just rely on temp folder cleanup on restart?
                                            # User requested: "After install 100% and Done -> delete".
                                            pass
                                        except: pass
                                    
                                    return # Success! Stop retrying.

                                if resp.get("success", False) == False:
                                    err_code = resp.get("error_code", 0)
                                    msg_text = str(resp).lower()
                                    
                                    # DEBUG: Log full error response for diagnosis
                                    log(f"API Error Response for {key}: {resp}", "ERROR")

                                    if isinstance(err_code, str): # Handle hex string if needed
                                        try: err_code = int(err_code, 16)
                                        except: pass
                                    
                                    # 0x80990024 = ALREADY INSTALLED / TASK EXISTS (GoldHEN/RPI)
                                    if err_code == 0x80990024 or "exists" in msg_text or "already" in msg_text:
                                         # FIX: Overwrite Logic
                                         if self.chk_overwrite.isChecked():
                                             log(f"Overwrite: 'Already Installed' detected. Uninstalling {tid}...", "WARN")
                                             server_signals.install_status.emit(key, "CHECKING", self.t("confirm_uninstall") + "...") # Reusing "Uninstall" text roughly
                                             
                                             try:
                                                 u_url = f"http://{ip}:{active_port}/api/uninstall"
                                                 self.http_session.post(u_url, json={"title_id": tid}, timeout=5)
                                                 time.sleep(3.0) # Wait for uninstall
                                                 
                                                 # Retry Install
                                                 log("Overwrite: Retrying installation...", "INFO")
                                                 r_retry = self.http_session.post(u_url, json={"type": "direct", "packages": [p_url]}, headers=headers, timeout=30)
                                                 
                                                 if r_retry.status_code == 200:
                                                     # Parse retry response
                                                     raw_retry = r_retry.text
                                                     clean_retry = re.sub(r'0x([0-9a-fA-F]+)', lambda m: str(int(m.group(0), 16)), raw_retry)
                                                     resp_retry = json.loads(clean_retry)
                                                     
                                                     if resp_retry.get("success", False) == True:
                                                         log(f"Overwrite Success for {key}", "INFO")
                                                         server_signals.install_status.emit(key, "QUEUE", "")
                                                         return 
                                                     else:
                                                         log(f"Overwrite Retry Failed: {resp_retry}", "ERROR")
                                                 else:
                                                     log(f"Overwrite Retry HTTP Error: {r_retry.status_code}", "ERROR")
                                             except Exception as e_ovr:
                                                 log(f"Overwrite Exception: {e_ovr}", "ERROR")

                                         server_signals.install_status.emit(key, "ALREADY", "")
                                         return
                                         
                                    # Check for no space
                                    if "no space" in msg_text or "disk full" in msg_text or err_code == 0x80990004:
                                         server_signals.install_status.emit(key, "SKIPPED_NO_SPACE", "")
                                         return
                                    
                                    
                                    # Default error message
                                    err_msg = f"Error {hex(err_code) if isinstance(err_code, int) else err_code}"
                                    
                                    if err_code == 0xFFFFFFFF:
                                        err_msg = "Install Failed (0xFFFFFFFF). File invalid or App running."
                                        if self.current_lang == "ru": err_msg = "Ошибка (0xFFFFFFFF). Файл поврежден или приложение запущено."
                                    elif err_code == 0x80020012: 
                                        err_msg = "Install Failed (0x80020012)."
                                    elif "0xffffff9d" in str(err_code).lower():
                                         err_msg = "SPPI Rejected (0x9D). Try RPI."

                                    server_signals.install_status.emit(key, "ERROR", err_msg)
                                    return
                                    
                            except Exception as json_err:
                                log(f"JSON Parse Error: {json_err}. Raw: {r.text}", "WARN")
                                if "success" in r.text:
                                    server_signals.install_status.emit(key, "QUEUE", "")
                                    # Removed finish_item_processing to wait for 100% progress
                                    return
                                server_signals.install_status.emit(key, "ERROR", "Bad API Response")
                                return
                        else:
                            server_signals.install_status.emit(key, "ERROR", f"HTTP {r.status_code}")
                            return

                    except requests.exceptions.Timeout:
                        # FIX: Smart Timeout - If download started, ignore API timeout
                        has_started = key in self.progress_map and self.progress_map.get(key, 0) > 0
                        if has_started:
                             log(f"API Timeout ignored (Download started for {key})", "WARN")
                             server_signals.install_status.emit(key, "QUEUE", "")
                             return
                        
                        server_signals.install_status.emit(key, "ERROR", self.t("timeout"))
                        return
                    except Exception as e:
                        log(f"Request Error: {e}", "ERROR")
                        server_signals.install_status.emit(key, "ERROR", str(e))
                        return

            except Exception as e:
                err_str = str(e)
                log(f"Worker Error: {e}", "ERROR")
                if "Expecting" in err_str:
                     server_signals.install_status.emit(key, "ERROR", "Connection Error (JSON)")
                else:
                     server_signals.install_status.emit(key, "ERROR", err_str)
        
        threading.Thread(target=wrk, daemon=True).start()

    def handle_install_status(self, key, status, msg):
        it = QTreeWidgetItemIterator(self.tree); target_item = None
        while it.value():
            if it.value().data(0, Qt.ItemDataRole.UserRole + 1) == key: target_item = it.value(); break
            it += 1
        if not target_item: return
        
        pb = self.tree.itemWidget(target_item, 7)
        st = self.tree.itemWidget(target_item, 8)
        btn_widget = self.tree.itemWidget(target_item, 9)
        is_visible = self.is_item_visible_in_tree(target_item)
        
        if status == "CHECKING":
             if st: st.setText(msg if msg else self.t("checking")); st.setStyleSheet("color: #aaa;")
             if pb: pb.setValue(0); 
             if is_visible and pb: pb.setVisible(True)
        elif status == "START":
            if pb: pb.setValue(0); 
            if is_visible and pb: pb.setVisible(True)
            if st: st.setText(self.t("sending").format(0)); st.setStyleSheet(STATUS_STYLES["Installing"])
        elif status == "QUEUE":
            # FIX: Don't overwrite "Done" if race condition (download finished before API return)
            is_already_done = False
            if st:
                txt = st.text().lower()
                if "done" in txt or "завершено" in txt or "completed" in txt:
                    is_already_done = True
            
            if not is_already_done:
                if st: st.setText(self.t("sent")); st.setStyleSheet(STATUS_STYLES["Installed"])
                self.lbl_sys.setText(self.t("sent"))
            else:
                # Still ensure we track it as finished if needed, though update_progress likely handled it
                pass
            
            # Страховочный таймер: если через 15 секунд прогресс не начался,
            # считаем что PS4 скачала файл молча (особенно для малых файлов)
            QTimer.singleShot(15000, lambda k=key: self.check_stalled_download(k))

        elif status == "ALREADY":
            if st: st.setText(self.t("already")); st.setStyleSheet(STATUS_STYLES["AlreadyInstalled"])
            target_item.setText(6, "-")
            if pb: pb.setValue(100); 
            if is_visible and pb: pb.setVisible(True)
            if btn_widget: btn_widget.setVisible(False) 
            if key not in self.finished_unique_keys: self.finished_unique_keys.add(key)
            QTimer.singleShot(100, lambda: self.finish_item_processing(target_item))
        elif status == "ERROR":
            if st: st.setText(msg if msg else self.t("error")); st.setToolTip(msg); st.setStyleSheet(STATUS_STYLES["Error"])
            target_item.setText(6, "-")
            if key not in self.finished_unique_keys: self.finished_unique_keys.add(key)
            if btn_widget: btn_widget.setVisible(False)
            QTimer.singleShot(500, lambda: self.finish_item_processing(target_item))
        elif status == "SKIPPED_NO_SPACE":
            if st: st.setText(self.t("skipped_no_space")); st.setStyleSheet(STATUS_STYLES["Skipped"])
            target_item.setText(6, "-")
            if pb: pb.setValue(0); pb.setVisible(False)
            if key not in self.finished_unique_keys: self.finished_unique_keys.add(key)
            if btn_widget: btn_widget.setVisible(False)
            QTimer.singleShot(100, lambda: self.finish_item_processing(target_item))
        
        self.save_pinned_data()
        self.recalc_global_stats()

    def finish_item_processing(self, item_to_remove=None):
        """Handle item completion and start next in queue."""
        if item_to_remove in self.active_installs:
            self.active_installs.remove(item_to_remove)

        if not self.install_queue and not self.active_installs:
            self.is_processing_queue = False
            if not self.is_global_paused:
                self.lbl_sys.setText(self.t("ready"))
            else:
                self.lbl_sys.setText(self.t("queue_paused"))
            self.countdown_timer.stop()
            return
            
        if self.is_global_paused:
            return

        # Start countdown for NEXT item if queue not empty
        if self.install_queue and not self.countdown_timer.isActive():
            self.countdown_val = 5 
            self.lbl_sys.setText(self.t("report_wait").format(self.countdown_val))
            self.countdown_timer.start(1000)
        elif not self.install_queue:
            self.lbl_sys.setText(self.t("ready"))

    def tick_countdown(self):
        # FIX: Robustness - check state again during countdown
        if not self.install_queue or self.is_global_paused:
            self.countdown_timer.stop()
            self.lbl_sys.setText(self.t("ready") if not self.is_global_paused else self.t("queue_paused"))
            return

        self.countdown_val -= 1
        if self.countdown_val <= 0:
            self.countdown_timer.stop()
            self.process_next_in_queue()
        else: self.lbl_sys.setText(self.t("report_wait").format(self.countdown_val))
    
    def check_stalled_download(self, key):
        """
        Страховочная проверка для файлов, которые PS4 скачала без прогресса.
        Вызывается через 15 секунд после QUEUE.
        Если прогресс так и не начался - завершаем файл.
        """
        # Ищем файл
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole + 1) == key:
                st = self.tree.itemWidget(item, 8)
                if not st:
                    break
                    
                txt = st.text().lower()
                
                # Проверяем: все еще статус "ссылка принята" и прогресс 0 или отсутствует?
                is_still_queued = "принята" in txt or "sent" in txt
                has_no_progress = key not in self.progress_map or self.progress_map.get(key, 0) == 0
                
                if is_still_queued and has_no_progress:
                    # PS4 скачала молча - завершаем
                    pb = self.tree.itemWidget(item, 7)
                    btn_widget = self.tree.itemWidget(item, 9)
                    
                    if st: 
                        st.setText(self.t("done"))
                        st.setStyleSheet(STATUS_STYLES["Installed"])
                    if pb: 
                        pb.setValue(100)
                        pb.setVisible(True)
                    if btn_widget: 
                        btn_widget.setVisible(False)
                    item.setText(6, "-")
                    
                    # Помечаем как завершенный и переходим к следующему
                    if key not in self.finished_unique_keys:
                        self.finished_unique_keys.add(key)
                        self.finish_item_processing(item)
                    
                    self.recalc_global_stats()
                break
            it += 1

    def update_progress(self, key, pct):
        # FIX: Check for cancellation first to prevent zombie updates
        if get_file_state(key) == "CANCELLED":
            return

        # FIX: Monotonic progress - only update if new value is >= current (prevent backwards jumps)
        current_pct = self.progress_map.get(key, 0)
        if pct < current_pct:
            return  # Ignore lower progress values (can happen with concurrent range requests)
        
        self.progress_map[key] = pct
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole + 1) == key:
                pb = self.tree.itemWidget(item, 7); st = self.tree.itemWidget(item, 8); btn_widget = self.tree.itemWidget(item, 9)
                
                is_done = False
                if st:
                    txt = st.text().lower()
                    # Исключаем "не установлено" / "not installed"
                    is_installed_ru = "установлено" in txt and "не" not in txt
                    is_installed_en = "installed" in txt and "not" not in txt
                    if "already" in txt or "done" in txt or "завершено" in txt or "ранее" in txt or is_installed_ru or is_installed_en:
                        is_done = True
                        if btn_widget: btn_widget.setVisible(False)
                        if pb: pb.setVisible(True); pb.setValue(100)
                        self.progress_map[key] = 100
                
                if not is_done:
                    if pb: 
                        pb.setValue(pct)
                        if not pb.isVisible() and self.is_item_visible_in_tree(item): pb.setVisible(True)
                    if btn_widget and self.is_item_visible_in_tree(item): btn_widget.setVisible(True)
                    
                    if st and self.t("done") not in st.text(): 
                        st.setText(self.t("sending").format(pct)); st.setStyleSheet(STATUS_STYLES["Installing"])
                    
                    if pct >= 100:
                        if st: st.setText(self.t("done")); st.setStyleSheet(STATUS_STYLES["Installed"])
                        if btn_widget: btn_widget.setVisible(False)
                        # FIX: Remove from speed tracking to stop updates, but keep displayed speed as final average
                        if key in self.speed_map: del self.speed_map[key]
                        if key not in self.finished_unique_keys: 
                            self.finished_unique_keys.add(key)
                            self.finish_item_processing(item)
                else:
                    self.recalc_global_stats()
                    return
                break
            it += 1
        self.recalc_global_stats()

    def toggle_global_pause(self, checked):
        self.is_global_paused = checked
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if key:
                s_key = str(key)
                state = get_file_state(s_key)
                if checked:
                    if state == "RUNNING":
                         self.toggle_item_pause(item, s_key, None)
                else:
                    if state == "PAUSED":
                        self.toggle_item_pause(item, s_key, None)
            it += 1
            
        if checked:
            self.btn_global_pause.setText(self.t("resume_global"))
            self.lbl_sys.setText(self.t("queue_paused"))
        else:
            self.btn_global_pause.setText(self.t("pause_global"))
            self.lbl_sys.setText(self.t("queue_resumed"))
            if not self.active_installs:
                self.process_next_in_queue()

    def cancel_all_operations(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(self.t("confirm_title"))
        msg.setText(self.t("confirm_cancel_all"))
        msg.setIcon(QMessageBox.Icon.Question)
        btn_confirm = msg.addButton(self.t("btn_yes"), QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(self.t("btn_no"), QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        if msg.clickedButton() != btn_confirm: return

        self.active_installs.clear()
        self.is_global_paused = True  # FIX: Force pause to prevent tick_countdown from restarting queue
        self.install_queue.clear()
        self.countdown_timer.stop()
        self.countdown_val = 0
        
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if key:
                st = self.tree.itemWidget(item, 8)
                if st:
                    txt = st.text()
                    if self.t("already") in txt or self.t("done") in txt or self.t("installed") in txt or "Завершено" in txt or "Ранее установлено" in txt:
                        it += 1; continue
                
                self.cancel_item(item, str(key))
            it += 1
        
        self.recalc_global_stats()
        self.lbl_sys.setText(self.t("cancelled"))
        # FIX: Update pause button to indicate paused state
        self.btn_global_pause.setChecked(True)
        self.btn_global_pause.setText(self.t("resume_global"))

    def toggle_item_pause(self, item, file_key, btn):
        st = self.tree.itemWidget(item, 8)
        if st and (self.t("done") in st.text() or self.t("already") in st.text()): return
        if not btn:
            widget = self.tree.itemWidget(item, 9)
            if widget and widget.layout().count() > 0: btn = widget.layout().itemAt(0).widget()
        
        current_state = get_file_state(str(file_key))
        
        # PAUSE
        if current_state == "RUNNING":
            if st:
                item.setData(0, Qt.ItemDataRole.UserRole + 10, st.text())       
                item.setData(0, Qt.ItemDataRole.UserRole + 11, st.styleSheet())
            set_file_state(str(file_key), "PAUSED")
            if btn: btn.setText("▶")
            if st: st.setText(self.t("paused")); st.setStyleSheet(STATUS_STYLES["Paused"])
            
        # RESUME
        elif current_state == "PAUSED":
            set_file_state(str(file_key), "RUNNING")
            if btn: btn.setText("⏸")
            saved_text = item.data(0, Qt.ItemDataRole.UserRole + 10)
            saved_style = item.data(0, Qt.ItemDataRole.UserRole + 11)
            if st:
                if saved_text:
                    st.setText(saved_text); st.setStyleSheet(saved_style if saved_style else STATUS_STYLES["Installing"])
                else:
                    st.setText(self.t("installing")); st.setStyleSheet(STATUS_STYLES["Installing"])
            if not self.is_processing_queue and item in self.install_queue:
                 if self.install_queue.index(item) == 0: self.process_next_in_queue()

    def cancel_item(self, item, file_key):
        set_file_state(str(file_key), "CANCELLED")
        if item in self.install_queue: self.install_queue.remove(item)
        st = self.tree.itemWidget(item, 8)
        if st: st.setText(self.t("cancelled")); st.setStyleSheet(STATUS_STYLES["Cancelled"])
        item.setText(6, "-") # Clear speed
        pb = self.tree.itemWidget(item, 7)
        if pb: pb.setValue(0); pb.setVisible(False)
        btn_widget = self.tree.itemWidget(item, 9)
        if btn_widget: btn_widget.setVisible(False)
        self.recalc_global_stats()
        if self.is_processing_queue: QTimer.singleShot(500, self.finish_item_processing)

    def on_loader_root(self, path, name, depth, is_startup, theme_type):
        path = os.path.normpath(path)
        if path in self.folder_items_map: return 
        
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            # Use normpath for comparison to handle existing items correctly
            if os.path.normpath(item.text(0).split(" ", 1)[-1]) == path:
                self.folder_items_map[path] = item
                if is_startup: item.setExpanded(False)
                return
        parent_item = None
        parent_dir = os.path.dirname(path)
        if parent_dir in self.folder_items_map: parent_item = self.folder_items_map[parent_dir]
        scope = parent_item if parent_item else self.tree.invisibleRootItem()
        item = QTreeWidgetItem(scope)
        prefix = "📌" if path in self.pinned_folders else "📁"
        item.setText(0, f"{prefix} {path}")
        colors = DEPTH_COLORS_LIGHT if theme_type == "light" else DEPTH_COLORS_DARK
        item.setForeground(0, QBrush(QColor(colors[depth % 5])))
        if is_startup: 
            item.setExpanded(False)
            if self.chk_hide_pinned.isChecked() and path in self.pinned_folders: item.setHidden(True)
        else: item.setExpanded(True)
        self.folder_items_map[path] = item
        if path in self.pinned_folders and self.chk_hide_pinned.isChecked(): item.setHidden(True)

    def on_loader_file(self, parent_path, name, tid, ver, region, category, size, full_path):
        full_path = os.path.normpath(full_path)
        if full_path in self.added_files_set: return
        self.added_files_set.add(full_path)

        # Normalize metadata for robust comparison
        tid = tid.strip().upper() if tid else None
        cat_upper = category.upper()
        # Heuristic for Theme detection if SFO category is generic 'gw' but file ends with '_1.pkg' or user says so
        # But usually Themes are 'gw' too. We might rely on filename or explicit category if customized.
        # User says "Themes". Check filename for "THEME" (case-insensitive).
        
        is_theme = "THEME" in name.upper()
        
        is_child_cat = cat_upper in ["UPDATE", "PATCH", "GP", "DLC", "AC", "ADDON", "THEME", "SD"]
        is_game_cat = cat_upper in ["GAME", "GD"] and not is_theme

        # VISUAL FIX: If detected as Theme but SFO says 'GW'/'GD', force 'THEME' display
        if is_theme: category = "THEME"

        real_parent = None
        if parent_path == "ROOT_MISC":
            real_parent = self.tree.invisibleRootItem()
            # USE MAP FOR O(1) LOOKUP if parent exists
            if tid and (is_child_cat or is_theme):
                if tid in self.tid_to_item_map:
                    real_parent = self.tid_to_item_map[tid]
                    real_parent.setExpanded(True)
        else:
            parent_path = os.path.normpath(parent_path)
            if parent_path not in self.folder_items_map: return
            real_parent = self.folder_items_map[parent_path]

        f = QTreeWidgetItem(real_parent)
        
        file_key = str(hash(name) & 0xFFFFFFFF)
        f.setData(0, Qt.ItemDataRole.UserRole + 1, file_key)
        
        if parent_path == "ROOT_MISC": 
             f.setText(0, f"📄 {name}") 
        else: 
             f.setText(0, f"  ┗ {name}")
        
        f.setText(1, tid if tid else "-"); f.setText(2, ver); f.setText(3, format_size(size))
        f.setText(4, region); f.setText(5, category); f.setText(6, "-")
        
        # Hidden Rank Column (10) for Sorting: 
        # GAME(0) -> UPDATE(1) -> THEME(2) -> DLC(3)
        # Also append filename to ensure _1 comes before _2
        rank = "4"
        if is_game_cat: rank = "0"
        elif cat_upper in ["UPDATE", "PATCH", "GP"]: rank = "1"
        elif is_theme: rank = "2"
        elif cat_upper in ["DLC", "AC", "ADDON"]: rank = "3"
        
        f.setText(10, f"{rank}_{name.lower()}")

        for c in range(1, 10): f.setTextAlignment(c, Qt.AlignmentFlag.AlignCenter)
        f.setData(0, Qt.ItemDataRole.UserRole, (name, tid, full_path))
        
        self.file_map[file_key] = full_path; self.file_map[name] = full_path
        self.file_sizes_map[file_key] = size 
        self.setup_item_widgets(f, full_path, file_key)
        
        log(f"Loaded: {name} ({format_size(size)})", "DEBUG")
        
        # Phase 5: Adoption Logic (If we just added a GAME, check for orphans)
        if is_game_cat and tid:
            self.tid_to_item_map[tid] = f # Store for future children
            
            # Expand search area for orphans - sometimes they might be inside "ROOT_MISC" item 
            # or already tucked away somewhere else. 
            # But let's stick to root level for now as per user screenshot.
            root = self.tree.invisibleRootItem()
            orphans = []
            for i in range(root.childCount()):
                item = root.child(i)
                i_tid = item.text(1).strip().upper()
                i_cat = item.text(5).upper()
                is_i_child = i_cat in ["UPDATE", "PATCH", "GP", "DLC", "AC", "ADDON", "THEME", "SD"]
                
                if item is not f and i_tid == tid and is_i_child:
                    orphans.append(item)
            
            for o in orphans:
                index = root.indexOfChild(o)
                if index != -1:
                    child = root.takeChild(index)
                    f.addChild(child)
                    f.setExpanded(True)
                    # FIX: RE-SETUP WIDGETS after move as they are lost on takeChild
                    o_key = o.data(0, Qt.ItemDataRole.UserRole + 1)
                    o_data = o.data(0, Qt.ItemDataRole.UserRole)
                    if o_key and o_data:
                        # Unpack name, tid, path from UserRole
                        # Data was stored as (name, tid, full_path) in line 5116
                        self.setup_item_widgets(o, o_data[2], o_key)
        
        # Removed recalc_global_stats from here to prevent O(N^2) on large loads.
        # It is now called once per batch in on_loader_batch and at the end in on_loader_finished.
    
        # Merged into main on_loader_finished below

    def setup_item_widgets(self, item, full_path, file_key):
        pb = QProgressBar()
        pb.setStyleSheet("""
            QProgressBar { border: none; text-align: center; background-color: transparent; color: white; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #05B8CC, stop:1 #27ae60); }
        """)
        pb.setVisible(False)

        st = QLabel(self.t("not_installed"))
        st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        st.setStyleSheet(STATUS_STYLES["NotInstalled"])

        btn_widget = QWidget()
        h = QHBoxLayout(btn_widget)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        
        btn_pause = QToolButton()
        btn_pause.setText("⏸")
        btn_pause.setFixedSize(24, 20)
        btn_pause.clicked.connect(lambda _, x=item, k=file_key, b=btn_pause: self.toggle_item_pause(x, k, b))
        
        btn_cancel = QToolButton()
        btn_cancel.setText("✖")
        btn_cancel.setFixedSize(24, 20)
        btn_cancel.clicked.connect(lambda _, x=item, k=file_key: self.cancel_item(x, k))
        
        h.addWidget(btn_pause)
        h.addWidget(btn_cancel)

        should_show_buttons = True # Default show
        if full_path in self.pinned_data_cache:
            state = self.pinned_data_cache[full_path]
            txt = state.get("text", "")
            st.setText(txt)
            st.setStyleSheet(state.get("style", ""))
            prog = state.get("progress", 0)
            if prog > 0:
                pb.setValue(prog)
                pb.setVisible(True)
                self.progress_map[file_key] = prog
            
            is_done = "already" in txt.lower() or "done" in txt.lower() or "installed" in txt.lower() or "установлено" in txt.lower() or "завершено" in txt.lower() or "ранее" in txt.lower()
            if is_done: should_show_buttons = False
        
        btn_widget.setVisible(should_show_buttons)
        self.tree.setItemWidget(item, 7, pb)
        self.tree.setItemWidget(item, 8, st)
        self.tree.setItemWidget(item, 9, btn_widget)

    def on_large_font_toggled(self): self.update_style()
    def update_style(self):
        theme_name = self.theme_combo.currentText()
        t = THEMES.get(theme_name, THEMES["Dark (Default)"])
        is_light = t.get("type") == "light"
        input_bg = t["input_bg"]; input_fg = t["input_fg"]
        darker_btn = QColor(t['btn_bg']).darker(115).name()
        font_size = "15px" if self.chk_large_font.isChecked() else "13px"
        base_font = f"font-size: {font_size};"
        self.grid_delegate.row_height = 36 if self.chk_large_font.isChecked() else 30
        
        css = f"""
            QMainWindow, QDialog {{ background-color: {t['bg']}; color: {t['fg']}; {base_font} }}
            QWidget, QLabel {{ color: {t['fg']}; {base_font} }}
            QLabel#statsLabel {{ border: 1px solid {t['input_border']}; border-radius: 4px; padding: 2px 6px; margin-left: 2px; background-color: {input_bg}; }}
            QLineEdit, QSpinBox {{ background-color: {input_bg}; color: {input_fg}; border: 1px solid {t['input_border']}; {STD_INPUT} {base_font} }}
            QComboBox {{ background-color: {input_bg}; color: {input_fg}; border: 1px solid {t['input_border']}; padding: 4px; {base_font} }}
            QComboBox QAbstractItemView {{ background-color: {input_bg}; color: {input_fg}; selection-background-color: {t['btn_bg']}; selection-color: {t['fg']}; }}
            QComboBox QAbstractItemView::item:hover {{ background-color: #ADD8E6; color: #000000; }}
            QCheckBox, QTreeView::indicator {{ color: {t['fg']}; spacing: 5px; {base_font} }}
            QCheckBox::indicator, QTreeView::indicator {{ width: 16px; height: 16px; border: 1px solid {t['input_border']}; border-radius: 3px; }}
            QCheckBox::indicator:unchecked {{ background-color: {input_bg}; }}
            QCheckBox::indicator:checked {{ background-color: #27ae60; border: 1px solid #27ae60; }}
            QPushButton {{ 
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['btn_bg']}, stop:1 {darker_btn}); 
                color: {t['btn_fg']}; border: 1px solid {t['input_border']}; border-bottom: 2px solid {t['input_border']}; border-radius: 4px; {MODERN_BTN} {base_font} 
            }}
            QPushButton:hover {{ background-color: {t['input_border']}; border-bottom: 2px solid {t['fg']}; }}
            QPushButton:pressed {{ border-bottom: 0px solid; margin-top: 2px; }}
            QMenu {{ background-color: {t['bg']}; border: 1px solid {t['input_border']}; {base_font} }}
            QMenu::item {{ padding: 8px 25px 8px 25px; background-color: transparent; color: {t['fg']}; }}
            QMenu::item:selected {{ background-color: {t['btn_bg']}; color: {t['fg']}; }}
            QTreeWidget {{ background-color: {t['tree_bg']}; color: {t['fg']}; alternate-background-color: {t['tree_alt']}; border: 1px solid {t['input_border']}; {base_font} }}
            QHeaderView::section {{ background-color: {t['header_bg']}; color: {t['fg']}; border: 1px solid {t['input_border']}; {STD_HEADER} {base_font} }}
            QGroupBox {{ border: 1px solid {t['input_border']}; margin-top: 10px; padding-top: 10px; color: {t['fg']}; font-weight: bold; {base_font} }}
            QFrame#statusFrame {{ background-color: {input_bg}; border-top: 1px solid {t['input_border']}; }}
            QPushButton#ctrlBtn {{ background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['btn_bg']}, stop:1 {darker_btn}); color: {t['btn_fg']}; border: 1px solid {t['input_border']}; border-bottom: 2px solid {t['input_border']}; {MODERN_BTN} {base_font} }}
        """
        self.grid_delegate.color = QColor(t['input_border'])
        final_css = css + ICON_BTN_STYLE + SPINBOX_FIX
        if self.current_bg_path and os.path.exists(self.current_bg_path):
            path_esc = self.current_bg_path.replace("\\", "/")
            bg_css = f"""QTreeWidget {{ border-image: url("{path_esc}") 0 0 0 0 stretch stretch; background-color: transparent; color: #e0e0e0; border: 1px solid #333; }}"""
            self.setStyleSheet(final_css); self.tree.setStyleSheet(bg_css)
        else: self.setStyleSheet(final_css); self.tree.setStyleSheet("") 
        
        root = self.tree.invisibleRootItem()
        colors = DEPTH_COLORS_LIGHT if is_light else DEPTH_COLORS_DARK
        def update_items_recursive(item, depth):
            if "📁" in item.text(0) or "📌" in item.text(0): item.setForeground(0, QBrush(QColor(colors[depth % 5])))
            for i in range(item.childCount()): update_items_recursive(item.child(i), depth + 1)
        for i in range(root.childCount()): update_items_recursive(root.child(i), 0)

    def set_background_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Выбрать фон", "", "Images (*.png *.jpg *.jpeg)")
        if fname: self.current_bg_path = fname; self.settings.setValue("bg_image", fname); self.update_style()
    def clear_background(self): self.current_bg_path = ""; self.settings.remove("bg_image"); self.update_style()
    
    def load_config(self):
        self.restoreGeometry(self.settings.value("geometry", b""))
        self.ip_input.setEditText(self.settings.value("ps4_ip", ""))
        self.port_input.setText(self.settings.value("server_port", "8337"))
        self.chk_hide_pinned.setChecked(str(self.settings.value("hide_pinned", "false")).lower() == "true")
        self.theme_combo.setCurrentText(self.settings.value("theme", "Dark (Default)"))
        self.chk_large_font.setChecked(self.settings.value("large_font", False, type=bool))
        self.current_bg_path = self.settings.value("bg_image", "")
        self.update_style()
        for i in range(8):
            w = self.settings.value(f"col_{i}", -1)
            if int(w) > 0: self.tree.setColumnWidth(i, int(w))
            else:
                if i==0: self.tree.setColumnWidth(i, 400)
                elif i==6: self.tree.setColumnWidth(i, 110)
                else: self.tree.setColumnWidth(i, 80)
                
    def update_pinned_visibility(self):
        should_hide = self.chk_hide_pinned.isChecked()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if "📌" in item.text(0): item.setHidden(should_hide)
            
    def load_pinned_data(self):
        if not os.path.exists("pinned.json"): return
        try:
            with open("pinned.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.pinned_folders = data.get("folders", [])
                self.pinned_data_cache = data.get("file_states", {})
        except: pass
        
    def save_pinned_data(self):
        file_states = {}
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data: 
                pb = self.tree.itemWidget(item, 5); st = self.tree.itemWidget(item, 6)
                if pb and st: file_states[data[2]] = {"text": st.text(), "style": st.styleSheet(), "progress": pb.value()}
            it += 1
        save_data = {"folders": self.pinned_folders, "file_states": file_states}
        try:
            with open("pinned.json", "w", encoding="utf-8") as f: json.dump(save_data, f, indent=4)
        except: pass

    def perform_shutdown_tasks(self):
        """Вспомогательный метод для сохранения настроек перед выходом"""
        self.save_pinned_data()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("ps4_ip", self.ip_input.currentText())
        
        self.settings.setValue("ps4_ip", self.ip_input.currentText())

        self.settings.setValue("server_port", self.port_input.text())
        self.settings.setValue("hide_pinned", self.chk_hide_pinned.isChecked())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("large_font", self.chk_large_font.isChecked())
        for i in range(8): self.settings.setValue(f"col_{i}", self.tree.columnWidth(i))
        if self.server_obj: self.server_obj.shutdown(); self.server_obj.server_close()
        if self.backup_thread: self.backup_thread.running = False; self.backup_thread.wait(1000)

    def closeEvent(self, e):
        # Если закрытие инициировано обновлением, пропускаем диалог
        if self.is_updating:
             self.perform_shutdown_tasks()
             e.accept()
             return

        dlg = CloseOptionDialog(self)
        dlg.setStyleSheet(self.styleSheet())
        dlg.exec()
        if dlg.result_code == 1: # Exit
            self.perform_shutdown_tasks()
            e.accept()
        elif dlg.result_code == 2: # Tray
            e.ignore()
            self.hide()
            if self.tray_icon.isVisible():
                msg = "Программа свернута в трей." if self.current_lang == "ru" else "App minimized to tray."
                self.tray_icon.showMessage("STORM PS4 SENDER", msg, QSystemTrayIcon.MessageIcon.Information, 2000)
        else: e.ignore()
        
    def on_loader_batch(self, batch_data):
        self.tree.setUpdatesEnabled(False)
        self.tree.setSortingEnabled(False)
        try:
            for item_data in batch_data:
                self.on_loader_file(*item_data)
        finally:
            self.tree.setUpdatesEnabled(True)
            
            # Update Progress Dialog (Marquee or Value)
            if hasattr(self, 'loading_progress') and self.loading_progress:
                # If multiple loaders are active, stick to marquee to avoid jitter
                if self.active_loaders > 1:
                    self.loading_progress.setRange(0, 0)
                elif self.loading_progress.maximum() > 0:
                    val = self.loading_progress.value() + len(batch_data)
                    self.loading_progress.setValue(val)
                
                QApplication.processEvents()

    def on_loader_finished(self):
        self.active_loaders -= 1
        if self.active_loaders > 0: return # Still other loaders running

        if hasattr(self, 'loading_progress') and self.loading_progress:
            self.loading_progress.close()
            self.loading_progress = None
        self.lbl_sys.setText(self.t("ready"))
        
        # FINAL GLOBAL ADOPTION PASS: To catch any orphans missed across batches/threads
        root = self.tree.invisibleRootItem()
        games = []
        # First, find all GAMES in the map
        for tid, game_item in self.tid_to_item_map.items():
            if game_item: games.append((tid, game_item))
            
        # Then, check all root children
        orphans_to_move = []
        for i in range(root.childCount()):
            item = root.child(i)
            i_tid = item.text(1).strip().upper()
            i_cat = item.text(5).upper()
            is_child = i_cat in ["UPDATE", "PATCH", "GP", "DLC", "AC", "ADDON"]
            if i_tid in self.tid_to_item_map and is_child:
                parent = self.tid_to_item_map[i_tid]
                if item is not parent:
                    orphans_to_move.append((item, parent))
        
        for item, parent in orphans_to_move:
            idx = root.indexOfChild(item)
            if idx != -1:
                child = root.takeChild(idx)
                parent.addChild(child)
                parent.setExpanded(True)
                # Ensure widgets restored after move
                i_key = item.data(0, Qt.ItemDataRole.UserRole + 1)
                i_data = item.data(0, Qt.ItemDataRole.UserRole)
                if i_key and i_data: self.setup_item_widgets(item, i_data[2], i_key)

        # FINAL SORTING: Use hidden column 10 for GAME -> UPDATE -> DLC order
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(10, Qt.SortOrder.AscendingOrder)
        
        self.update_pinned_visibility()
        self.recalc_global_stats()
        self.tid_to_item_map.clear()
        if self.active_loaders < 0: self.active_loaders = 0

    def show_loading_progress(self, msg, total=0):
        """Deduplicated progress dialog management."""
        self.active_loaders += 1
        if hasattr(self, 'loading_progress') and self.loading_progress:
            self.loading_progress.setLabelText(msg)
            # If we were in total mode but now have multiple threads, go back to marquee
            if self.active_loaders > 1: self.loading_progress.setRange(0, 0)
            return
            
        self.loading_progress = QProgressDialog(msg, self.t("cancel"), 0, total, self)
        self.loading_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.loading_progress.setMinimumDuration(0)
        self.loading_progress.setValue(0)
        geo = self.geometry()
        self.loading_progress.move(geo.center() - self.loading_progress.rect().center())
        self.loading_progress.show()

    def select_folder(self):
        # Fix: Use instance to center dialog
        dlg = QFileDialog(self, "Dir", "")
        # Restore last used path
        last_path = self.settings.value("last_folder_path", "")
        if last_path and os.path.exists(last_path): dlg.setDirectory(last_path)
            
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        if dlg.exec():
            # selectedFiles returns list, we need first
            p = dlg.selectedFiles()[0]
            self.settings.setValue("last_folder_path", p)
            self.lbl_sys.setText("Adding...")
            
            self.show_loading_progress(self.t("scan_folder"))
            
            theme = THEMES.get(self.theme_combo.currentText(), THEMES["Dark (Default)"])
            self.loader_thread_manual = LoaderThread([p], is_startup=False, theme_type=theme["type"], mode="folder", batch_size=20)
            self.loader_thread_manual.start()
            
    def select_files(self):
        # Fix: Use instance to center dialog
        dlg = QFileDialog(self, "Select PKG/BIN Files", "")
        # Restore last used path (files)
        last_path = self.settings.value("last_files_path", "")
        if last_path and os.path.exists(last_path): dlg.setDirectory(last_path)
        
        dlg.setNameFilter("Files (*.pkg *.bin)")
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if dlg.exec():
            files = dlg.selectedFiles()
            if not files: return
            
            # Save last path
            self.settings.setValue("last_files_path", os.path.dirname(files[0]))
            self.lbl_sys.setText("Adding files...")
            
            self.show_loading_progress(self.t("add_files"))
            
            theme = THEMES.get(self.theme_combo.currentText(), THEMES["Dark (Default)"])
            self.loader_thread_manual = LoaderThread(files, is_startup=False, theme_type=theme["type"], mode="files", batch_size=20)
            self.loader_thread_manual.start()
            
    # Removed custom eventFilter and keyPressEvent in favor of QAction
        
    def delete_selected(self):
        items = self.tree.selectedItems()
        if not items: return
        
        # Сначала собираем список путей папок для удаления из реестра
        folders_to_remove_from_map = []
        
        for item in items:
            # Очищаем данные файлов внутри
            self._clean_map_recursive(item)
            
            # Если это папка (корневой элемент или вложенная папка)
            # Нам нужно найти её путь и удалить из folder_items_map
            # Самый надежный способ - перебор map, так как text(0) содержит иконки
            for path, map_item in list(self.folder_items_map.items()):
                if map_item == item:
                    del self.folder_items_map[path]
            
            # Удаление из списка закрепленных
            txt = item.text(0).replace("📁 ", "").replace("📌 ", "").strip()
            if txt in self.pinned_folders: 
                self.pinned_folders.remove(txt)
            
            # Удаление визуальное
            (item.parent() or self.tree.invisibleRootItem()).removeChild(item)
            
        self.save_pinned_data()
        self.recalc_global_stats()
        
    def _clean_map_recursive(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        # Если это файл
        if data:
            if isinstance(data, (tuple, list)):
                 full_path = data[2] if len(data) > 2 else data[0]
            else:
                 full_path = data
            
            # Удаляем из кэша состояний
            if full_path in self.pinned_data_cache: 
                del self.pinned_data_cache[full_path]
            # КРИТИЧНО: Удаляем из сета добавленных файлов, чтобы можно было добавить снова
            norm_path = os.path.normpath(full_path)
            if norm_path in self.added_files_set: 
                self.added_files_set.remove(norm_path)
            
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if key: 
                s_key = str(key)
                set_file_state(s_key, "RUNNING")
                if s_key in self.file_sizes_map: del self.file_sizes_map[s_key]
                if s_key in self.progress_map: del self.progress_map[s_key]
                if s_key in self.speed_map: del self.speed_map[s_key]
        
        # Если это папка - чистим детей, а также удаляем саму папку из folder_items_map если она там есть
        else:
            # Проверяем, есть ли эта вложенная папка в карте папок
            for path, map_item in list(self.folder_items_map.items()):
                if map_item == item:
                    del self.folder_items_map[path]

        for i in range(item.childCount()): 
            self._clean_map_recursive(item.child(i))
        
    def update_speed(self, key, speed_val):
        # Skip speed updates for completed items
        if key in self.finished_unique_keys:
            return
        
        self.speed_map[key] = speed_val
        speed_str = format_size(speed_val) + "/s"
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole + 1) == key:
                # FIX: Check status column (8), not speed column (6)
                status_widget = self.tree.itemWidget(item, 8)
                if status_widget:
                    txt = status_widget.text().lower()
                    if self.t("already").lower() in txt or self.t("done").lower() in txt or "завершено" in txt:
                        return
                item.setText(6, speed_str)
                break
            it += 1
            
    def recalc_global_stats(self):
        total_files = 0; done_count = 0; error_count = 0; total_bytes = 0; downloaded_bytes = 0
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if key:
                total_files += 1
                s_key = str(key)
                f_size = self.file_sizes_map.get(s_key, 0)
                total_bytes += f_size
                st = self.tree.itemWidget(item, 8)
                if st:
                    txt = st.text()
                    if self.t("done") in txt or self.t("already") in txt or self.t("sent") in txt: done_count += 1; downloaded_bytes += f_size
                    elif self.t("error") in txt or self.t("timeout") in txt: error_count += 1
                    else: prog = self.progress_map.get(s_key, 0); downloaded_bytes += f_size * (prog / 100.0)
            it += 1
        self.global_progress.setRange(0, total_files)
        self.global_progress.setValue(done_count + error_count)
        chunk_color = "#27ae60"
        if error_count > 0: chunk_color = "#d35400"
        self.global_progress.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid #444; border-radius: 4px; text-align: center; background-color: #222; color: white; height: 18px; }} 
            QProgressBar::chunk {{ background-color: {chunk_color}; width: 1px; }}
        """)
        self.global_stats_label.setText(self.t("stat_total").format(total_files, done_count, error_count))
        self.size_stats_label.setText(self.t("stat_size").format(format_size(downloaded_bytes), format_size(total_bytes)))
        self.bytes_remaining = total_bytes - downloaded_bytes
        
    def update_eta_and_speed_labels(self):
        total_speed = sum(self.speed_map.values())
        keys_to_remove = []
        for k, v in self.speed_map.items():
            if get_file_state(k) != "RUNNING": keys_to_remove.append(k)
        for k in keys_to_remove: del self.speed_map[k]
        if total_speed > 0 and self.bytes_remaining > 0:
            seconds = self.bytes_remaining / total_speed
            eta_str = str(datetime.timedelta(seconds=int(seconds)))
            self.eta_label.setText(self.t("stat_eta").format(eta_str))
        else:
            if self.bytes_remaining <= 0: self.eta_label.setText(self.t("stat_eta").format("00:00:00"))
            else: self.eta_label.setText(self.t("stat_eta").format("--:--:--"))
            
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.accept()
        
    def dropEvent(self, e):
        folders = []; files = []
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if os.path.isdir(p): folders.append(p)
            elif os.path.isfile(p) and p.lower().endswith(('.pkg', '.bin')): files.append(p)
        if folders:
            self.show_loading_progress(self.t("scan_dropped_folders"))
            theme = THEMES.get(self.theme_combo.currentText(), THEMES["Dark (Default)"])
            self.loader_thread_drop_folders = LoaderThread(folders, is_startup=False, theme_type=theme["type"], mode="folder", batch_size=20)
            self.loader_thread_drop_folders.start()
        if files:
            self.show_loading_progress(self.t("add_dropped_files"))
            theme = THEMES.get(self.theme_combo.currentText(), THEMES["Dark (Default)"])
            self.loader_thread_drop_files = LoaderThread(files, is_startup=False, theme_type=theme["type"], mode="files", batch_size=20)
            self.loader_thread_drop_files.start()
        
    def show_status_msg(self, msg): self.lbl_sys.setText(msg)
    
    def start_server(self):
        if self.server_obj: self.server_obj.shutdown(); self.server_obj.server_close()
        try:
            port = int(self.port_input.text())
            self.server_port_val = port
            PS4HTTPHandler.map_files = self.file_map
            self.server_obj = ThreadedHTTPServer(('0.0.0.0', port), PS4HTTPHandler)
            threading.Thread(target=self.server_obj.serve_forever, daemon=True).start()
            self.server_status_ok = True; self.lbl_srv.setText(self.t("server_ok").format(port)); self.lbl_srv.setStyleSheet("color: #00FF00;")
        except:
            self.server_status_ok = False; self.lbl_srv.setText(self.t("server_err")); self.lbl_srv.setStyleSheet("color: red;")
    
    def extract_pkg_icon(self):
        """Extract icon from selected PKG."""
        items = self.tree.selectedItems()
        if not items: return
        
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        path = data[2] if isinstance(data, tuple) else data
        
        # Reuse extraction logic (simplified)
        self.show_cover_dialog(path, save_mode=True)

    def show_cover_dialog(self, pkg_path, save_mode=False):
        """Extract and show PKG cover using Brute Force Content Scan."""
        try:
            icon_data = None
            img_type = "png" 
            
            with open(pkg_path, "rb") as f:
                # Read header (16MB covers huge tables)
                header_size = 16 * 1024 * 1024 
                header_data = f.read(header_size) 
                
                # BRUTE FORCE SCANNNER
                # Instead of trying to parse the Entry Table (which is hard due to relative offsets),
                # we just look for ANY 32-bit integer that looks like a valid Offset to a PNG/JPG.
                
                # Valid Image Check
                def check_image(offset, size):
                    if offset >= len(header_data) or offset + size > len(header_data): return None
                    head = header_data[offset : offset + 8]
                    if head.startswith(b'\x89PNG\r\n\x1a\n'): return "png"
                    if head.startswith(b'\xff\xd8'): return "jpg"
                    return None
                
                found = False
                # Scan through the header (assuming 4-byte alignment, 4-byte stride)
                # We stop comfortably before end
                scan_limit = min(len(header_data), 4 * 1024 * 1024) # Scan first 4MB for entries
                
                # Collect ALL found images, then pick the smallest (icons are 50-200KB, backgrounds are 1-5MB)
                found_images = []  # [(offset, size, type), ...]
                
                for i in range(0, scan_limit, 4):
                    try:
                        # Assume 'i' is DataOffset field
                        # 'i+4' is DataSize field
                        val_off = struct.unpack('>I', header_data[i:i+4])[0]
                        val_sz = struct.unpack('>I', header_data[i+4:i+8])[0]
                        
                        # Heuristic Filter:
                        # Size: 100 bytes < size < 10MB
                        # Offset: Must be > 0 and point inside our buffer (for now)
                        if 100 < val_sz < 10 * 1024 * 1024 and val_off > 0:
                            # Does it point to an image?
                            itype = check_image(val_off, val_sz)
                            if itype:
                                found_images.append((val_off, val_sz, itype))
                    except: pass
                
                # Pick the SMALLEST image (icon0.png is typically 50-200KB, pic0/pic1 are 1-5MB)
                if found_images:
                    # Sort by size ascending
                    found_images.sort(key=lambda x: x[1])
                    best = found_images[0]
                    log(f"BruteForce: Found {len(found_images)} images. Picked smallest: Off:{best[0]} Sz:{best[1]} Type:{best[2]}", "INFO")
                    f.seek(best[0])
                    icon_data = f.read(best[1])
                    img_type = best[2]
                    found = True
                    
                if not found:
                     log("BruteForce Scan failed to find valid icon entry.", "WARN")

            if icon_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(icon_data):
                    
                    if save_mode:
                        # Save Mode (Context Menu)
                        save_path, _ = QFileDialog.getSaveFileName(self, self.t("ctx_extract_icon"), f"icon0.{img_type}", f"Images (*.{img_type})")
                        if save_path:
                            with open(save_path, "wb") as f_out: f_out.write(icon_data)
                            QMessageBox.information(self, self.t("done"), "Saved!")
                        return

                    # View Mode (Double Click)
                    dlg = QDialog(self)
                    dlg.setWindowTitle(self.t("icon_preview"))
                    
                    v = QVBoxLayout(dlg)
                    l = QLabel()
                    l.setPixmap(pixmap.scaled(512, 512, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    v.addWidget(l)
                    
                    # Info text
                    info = QLabel(f"Size: {len(icon_data)/1024:.1f} KB | Type: {img_type.upper()}")
                    info.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    v.addWidget(info)
                    
                    dlg.exec()
                else:
                     log("QPixmap load failed (corrupt data?)", "WARN")
                     QMessageBox.warning(self, "Error", "Failed to load image data.")
            else:
                if save_mode: QMessageBox.warning(self, self.t("error"), self.t("icon_header_err")) # Only warn on explicit extract
                else: log("Icon not found for preview", "WARN")

        except Exception as e:
            log(f"Icon Extract Error: {e}", "ERROR")

    def wide_input_dialog(self, title, label, text):
        """Helper for wider input dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLayout(QVBoxLayout())
        
        lbl = QLabel(label)
        dlg.layout().addWidget(lbl)
        
        inp = QLineEdit(text)
        inp.setMinimumWidth(400) # WIDER
        dlg.layout().addWidget(inp)
        
        btns = QDialogButtonBox()
        btn_ok = btns.addButton(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText(self.t("ok"))
        btn_cancel = btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_cancel.setText(self.t("cancel"))
        
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        dlg.layout().addWidget(btns)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return inp.text(), True
        return "", False

    def rename_pkg_file(self):
        """Rename selected PKG file."""
        items = self.tree.selectedItems()
        if not items: return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        old_path = data[2] if isinstance(data, tuple) else data
        
        if not old_path or not os.path.exists(old_path): return
        
        old_name = os.path.basename(old_path)
        new_name, ok = self.wide_input_dialog(self.t("ctx_rename_pkg"), self.t("rename_wide"), old_name)
        
        if ok and new_name and new_name != old_name:
            if not new_name.lower().endswith(".pkg"): new_name += ".pkg"
            
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                
                # Update UI
                if "📄" in item.text(0): item.setText(0, f"📄 {new_name}")
                elif "┗" in item.text(0): item.setText(0, f"  ┗ {new_name}")
                else: item.setText(0, new_name)
                
                # Update internal maps
                if isinstance(data, (tuple, list)):
                     tid = data[1] if len(data) > 1 else ""
                     item.setData(0, Qt.ItemDataRole.UserRole, (new_name, tid, new_path))
                else:
                     item.setData(0, Qt.ItemDataRole.UserRole, new_path)
                
                if old_name in self.file_map: del self.file_map[old_name]
                self.file_map[new_name] = new_path
                # Also check file_sizes_map if used
                if old_path in self.file_sizes_map:
                    self.file_sizes_map[new_path] = self.file_sizes_map.pop(old_path)
                
                log(f"Renamed: {old_name} -> {new_name}", "INFO")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Rename failed: {e}")

    def on_item_dbl_clicked(self, item, col):
        """Handle double click on main tree items."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        full_path = data[2] if isinstance(data, tuple) else data
        
        # Check if it is a PKG file
        if full_path and isinstance(full_path, str) and full_path.lower().endswith(".pkg"):
             self.show_cover_dialog(full_path)
             # Fix: Prevent auto-collapse on double click logic
             if item.childCount() > 0:
                  # Run this slightly after the double-click event is processed by the tree
                  QTimer.singleShot(100, lambda: item.setExpanded(True))

    def on_item_clicked(self, item, col):
        if col in [1, 2]:
            t = item.text(col); QGuiApplication.clipboard().setText(t); self.lbl_sys.setText(self.t("copy").format(t))
            
    def open_menu(self, pos):
        sel_items = self.tree.selectedItems()
        if sel_items:
            m = QMenu()
            potential_files = []; potential_folders = []
            for i in sel_items:
                data = i.data(0, Qt.ItemDataRole.UserRole)
                if data: potential_files.append((i, data[2]))
                else:
                    txt = i.text(0).replace("📁 ", "").replace("📌 ", "").strip()
                    potential_folders.append((i, txt))
            if potential_files:
                a_inst = QAction("🚀 " + self.t("install_sel").format(len(potential_files)), self)
                a_inst.triggered.connect(self.install_selected)
                if len(potential_files) == 1:
                    item = potential_files[0][0] # The QTreeWidget item
                    f_path = potential_files[0][1]
                    if f_path.lower().endswith(".pkg"):
                        a_icon = QAction(self.t("ctx_extract_icon"), self)
                        a_icon.triggered.connect(self.extract_pkg_icon)
                        m.addAction(a_icon)
                        
                        a_ren = QAction(self.t("ctx_rename_pkg"), self)
                        a_ren.triggered.connect(self.rename_pkg_file)
                        m.addAction(a_ren)
                        
                        m.addSeparator()
                        a_bp = QAction(self.t("backport_ctx"), self)
                        a_bp.triggered.connect(self.run_backport_action)
                        m.addAction(a_bp)
                    
                    a_open = QAction(self.t("ctx_folder"), self) # Icon is in locale
                    a_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(f_path))))
                    m.addAction(a_open)
                
                # CRITICAL: Add the Send Selected action to the menu
                m.addSeparator()
                m.addAction(a_inst)
                
            if potential_folders:
                m.addSeparator()
                if len(potential_folders) == 1:
                    item, txt = potential_folders[0]
                    if txt in self.pinned_folders:
                        a_pin = QAction(self.t("unpin"), self)
                        a_pin.triggered.connect(lambda: self.toggle_pin(item, txt, False))
                    else:
                        a_pin = QAction(self.t("pin"), self)
                        a_pin.triggered.connect(lambda: self.toggle_pin(item, txt, True))
                    m.addAction(a_pin)
                else:
                    a_pin_all = QAction(self.t("pin_sel").format(len(potential_folders)), self)
                    a_pin_all.triggered.connect(lambda: self.mass_pin_toggle(potential_folders, True))
                    a_unpin_all = QAction(self.t("unpin_sel").format(len(potential_folders)), self)
                    a_unpin_all.triggered.connect(lambda: self.mass_pin_toggle(potential_folders, False))
                    m.addAction(a_pin_all); m.addAction(a_unpin_all)
            m.addSeparator()
            a_del = QAction("🗑️ " + self.t("remove_list"), self)
            a_del.triggered.connect(self.delete_selected)
            m.addAction(a_del)
            m.exec(self.tree.viewport().mapToGlobal(pos))
            
    def mass_pin_toggle(self, folder_list, pin):
        for item, path in folder_list: self.toggle_pin(item, path, pin)
        
    def toggle_pin(self, item, path, pin):
        if pin:
            if path not in self.pinned_folders: self.pinned_folders.append(path)
            item.setText(0, f"📌 {path}")
        else:
            if path in self.pinned_folders: self.pinned_folders.remove(path)
            item.setText(0, f"📁 {path}")
        self.save_pinned_data()
        
    def install_selected(self):
        raw = self.tree.selectedItems()
        items_to_add = []; processed = set()
        for i in raw: self._collect_items_recursive(i, items_to_add, processed)
        self.prepare_queue(items_to_add)
        
    def install_all(self):
        if self.is_global_paused:
            self.is_global_paused = False
            self.btn_global_pause.setChecked(False)
            self.btn_global_pause.setText(self.t("pause_global"))
            self.lbl_sys.setText(self.t("queue_resumed"))
        
        # Use unified logic from recursive collector (same as Context Menu -> Install)
        items_to_add = []
        processed_paths = set()
        
        for i in range(self.tree.topLevelItemCount()):
            self._collect_items_recursive(self.tree.topLevelItem(i), items_to_add, processed_paths)
            
        # Filter out RUNNING/PAUSED items (extra safety before prepare_queue)
        final_items = []
        for item in items_to_add:
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            state = None
            if key: state = get_file_state(str(key))
            
            if state in ["RUNNING", "PAUSED"]:
                continue
            final_items.append(item)

        if not final_items:
            # Only show message if queue is also empty
            if not self.install_queue:
                 title = "Инфо" if getattr(self, "current_lang", "en") == "ru" else "Info"
                 msg = "Нет файлов для отправки." if getattr(self, "current_lang", "en") == "ru" else "No files to send."
                 QMessageBox.information(self, title, msg)
            return

        self.prepare_queue(final_items)
        
    def _collect_items_recursive(self, item, items_list, processed_paths):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
             # FIX: Robust check for tuple vs string data
             full_path = data[2] if isinstance(data, (tuple, list)) and len(data) > 2 else data
             
             if full_path and full_path not in processed_paths:
                st = self.tree.itemWidget(item, 8)
                should_add = True
                if st:
                    txt = st.text().lower()
                    
                    # --- IMPROVED STATUS CHECK ---
                    # Only skip if it's REALLY finished (installed or done)
                    is_installed_ru = "установлено" in txt and "не" not in txt
                    is_installed_en = "installed" in txt and "not" not in txt
                    
                    is_done = "done" in txt or "already" in txt or "завершено" in txt or "ранее" in txt or is_installed_ru or is_installed_en
                    
                    if is_done and not self.chk_overwrite.isChecked(): 
                        should_add = False
                        
                if should_add:
                    items_list.append(item); processed_paths.add(full_path)
        
        # ALWAYS check children (deep traversal) even if parent is a file (Game with nested Update/DLC)
        for i in range(item.childCount()): 
            self._collect_items_recursive(item.child(i), items_list, processed_paths)
            
    def prepare_queue(self, items):
        added_count = 0
        for item in items:
            if item not in self.install_queue:
                st = self.tree.itemWidget(item, 8)
                
                # Пропускаем, если уже в ожидании
                if st:
                    txt = st.text().lower()
                    if ("waiting" in txt or "ожидание" in txt) and item in self.install_queue: continue
                
                self.install_queue.append(item)
                if st: st.setText(self.t("waiting")); st.setStyleSheet("color: #aaa;")
                added_count += 1
        
        self.recalc_global_stats()
        
        # FIX: Reset state for items re-added to queue (e.g. Overwrite)
        for item in self.install_queue:
            key = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if key:
                s_key = str(key)
                if s_key in self.finished_unique_keys:
                    # Reset internal states
                    self.progress_map[s_key] = 0
                    if s_key in self.speed_map: del self.speed_map[s_key]
                    self.finished_unique_keys.remove(s_key)
                    
                    # Reset UI Elements
                    pb = self.tree.itemWidget(item, 7)
                    if pb: 
                        pb.setValue(0)
                        if self.is_item_visible_in_tree(item): pb.setVisible(True)
                    
                    item.setText(6, "-") # Speed column

        if added_count > 0:
            if not self.chk_overwrite.isChecked() and self.ip_input.currentText() and not self.installed_apps_cache:
                # FIX: Prevent crash if scanner is already running
                if self.silent_scanner and self.silent_scanner.isRunning():
                     log("Silent scan already running, skipping new request.", "DEBUG")
                else:
                    self.lbl_sys.setText("🔎 ...")
                    self.silent_scanner = SilentAppsScanner(self.ip_input.currentText())
                    self.silent_scanner.finished.connect(lambda: self.on_silent_scan_finished(self.installed_apps_cache))
                    self.silent_scanner.start()
            else:
                if not self.is_global_paused:
                    self.process_next_in_queue()
                    
    def on_silent_scan_finished(self, installed_db):
        self.installed_apps_cache = installed_db
        self.lbl_sys.setText(self.t("ready"))
        if not self.is_global_paused:
            self.process_next_in_queue()

    def show_logs_dialog(self):
        """Show a dialog with timestamped log entries."""
        from PyQt6.QtWidgets import QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("logs_title"))
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        
        # Copy logs from buffer
        with LOG_LOCK:
            log_text = "\n".join(LOG_BUFFER)
        
        if not log_text:
            log_text = self.t("logs_empty")
        
        text_edit.setPlainText(log_text)
        text_edit.verticalScrollBar().setValue(text_edit.verticalScrollBar().maximum())
        
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton(self.t("logs_copy"))
        btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(log_text))
        btn_layout.addWidget(btn_copy)
        
        btn_clear = QPushButton(self.t("logs_clear"))
        def clear_logs():
            with LOG_LOCK:
                LOG_BUFFER.clear()
            text_edit.setPlainText(self.t("logs_cleared"))
        btn_clear.clicked.connect(clear_logs)
        btn_layout.addWidget(btn_clear)
        
        btn_close = QPushButton(self.t("logs_close"))
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.exec()

    def show_column_visibility_menu(self, pos):
        """Show dialog to toggle column visibility with green checkboxes."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("col_visibility"))
        dialog.setMinimumWidth(250)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        
        self.col_checkboxes = []
        for i, name in enumerate(self.column_names):
            cb = QCheckBox(name)
            cb.setChecked(not self.tree.isColumnHidden(i))
            cb.setProperty("col_idx", i)
            cb.stateChanged.connect(lambda state, idx=i: self.toggle_column_visibility(idx, state == 2))
            layout.addWidget(cb)
            self.col_checkboxes.append(cb)
        
        btn_close = QPushButton(self.t("ok"))
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def toggle_column_visibility(self, column_idx, visible):
        """Toggle column visibility and save to settings."""
        self.tree.setColumnHidden(column_idx, not visible)
        self.save_column_visibility()

    def save_column_visibility(self):
        """Save column visibility state to settings."""
        visibility = ["1" if not self.tree.isColumnHidden(i) else "0" for i in range(10)]
        self.settings.setValue("column_visibility", ",".join(visibility))

    def switch_page(self, page_idx):
        """Switch to a different page in the stacked widget."""
        self.page_stack.setCurrentIndex(page_idx)
        self.update_sidebar_active(page_idx)

        # FTP Warning
        if page_idx == 1:
            show_warn = self.settings.value("show_ftp_warning", True, type=bool)
            if show_warn:
                dlg = QDialog(self)
                dlg.setWindowTitle(self.t("ftp_warning_title"))
                dlg.setModal(True)
                dlg.setStyleSheet(self.styleSheet())
                
                vbox = QVBoxLayout(dlg)
                vbox.setSpacing(15) 
                
                lbl_icon = QLabel("⚠️")
                lbl_icon.setStyleSheet("font-size: 40px; color: orange;")
                lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                vbox.addWidget(lbl_icon)
                
                lbl_text = QLabel(self.t("ftp_warning_text"))
                lbl_text.setWordWrap(True)
                lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
                vbox.addWidget(lbl_text)
                
                # Checkbox centered
                h_chk = QHBoxLayout()
                h_chk.addStretch()
                chk_show = QCheckBox(self.t("ftp_warning_chk"))
                chk_show.setChecked(False) # Start unchecked by default
                chk_show.setStyleSheet("QCheckBox::indicator:checked { background-color: #27ae60; border: 1px solid #27ae60; }")
                h_chk.addWidget(chk_show)
                h_chk.addStretch()
                vbox.addLayout(h_chk)
                
                btn_ok = QPushButton("OK")
                btn_ok.setFixedWidth(100) # Optional: make button nicer width
                btn_ok.clicked.connect(dlg.accept)
                
                # Center button too
                h_btn = QHBoxLayout()
                h_btn.addStretch(); h_btn.addWidget(btn_ok); h_btn.addStretch()
                vbox.addLayout(h_btn)
                
                dlg.exec()
                
                if chk_show.isChecked():
                     self.settings.setValue("show_ftp_warning", False)

    def update_sidebar_active(self, active_idx):
        """Update sidebar button styles to highlight active page."""
        for btn in self.sidebar_buttons:
            p = btn.property("page_idx")
            if p == active_idx:
                btn.setStyleSheet("background-color: #4CAF50; border-radius: 8px; font-size: 20px;")
            else:
                btn.setStyleSheet("background-color: #333; border-radius: 8px; font-size: 20px;")

    def run_backport_action(self):
        """Run the backport tool for the selected PKG."""
        items = self.tree.selectedItems()
        if not items: return
        
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        pkg_path = data[2] if isinstance(data, (tuple, list)) and len(data) > 2 else data
        
        if not pkg_path or not pkg_path.lower().endswith(".pkg"):
             QMessageBox.warning(self, "Error", "Select a PKG file first.")
             return
             
        dlg = BackportDialog(self, pkg_path)
        # Load last selection
        last_fw = self.settings.value("last_backport_fw", self.t("bp_all_fw"))
        idx = dlg.fw_combo.findText(last_fw)
        if idx >= 0: dlg.fw_combo.setCurrentIndex(idx)
        
        dlg.center_on_parent()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_fw = dlg.fw_combo.currentText()
            out_dir = dlg.path_input.text()
            
            # Save for next time
            self.settings.setValue("last_backport_fw", selected_fw)
            
            # 1. Determine target firmware(s)
            target_fws = []
            if selected_fw == self.t("bp_all_fw"):
                target_fws = dlg.fw_list
            elif selected_fw == self.t("bp_my_list"):
                saved_ml = self.settings.value("backport_my_list", "").split(",")
                target_fws = [fw for fw in saved_ml if fw.strip()]
            else:
                target_fws = [selected_fw]
            
            if not target_fws:
                 QMessageBox.warning(self, "Error", "No firmware versions selected.")
                 return
            
            # Ensure tools exist
            base_tools = resource_path("tools")
            
            # FIX: Copy ALL necessary tools to temp folder
            # FIX: Copy ALL necessary tools to temp folder with smart discovery
            try:
                temp_tools = os.path.join(tempfile.gettempdir(), "storm_tools")
                os.makedirs(temp_tools, exist_ok=True)
                
                # List of tools to copy
                # FIX: Copy ALL DLLs and EXEs to ensure dependencies (like orbis-pub-prx.dll) are present
                
                def copy_tools_from_dir(src_dir):
                    if not os.path.exists(src_dir): return
                    for fname in os.listdir(src_dir):
                        if fname.lower().endswith(".exe") or fname.lower().endswith(".dll"):
                            src_p = os.path.join(src_dir, fname)
                            dst_p = os.path.join(temp_tools, fname)
                            try:
                                shutil.copy2(src_p, dst_p)
                                log(f"Copied dependency: {fname}", "DEBUG")
                                
                                # NUCLEAR OPTION: Copy helpers to 'ext' subfolder too
                                if fname.lower() in ["sc.exe", "di.exe", "orbis-pub-sfo.exe"]:
                                     ext_dir = os.path.join(temp_tools, "ext")
                                     os.makedirs(ext_dir, exist_ok=True)
                                     shutil.copy2(src_p, os.path.join(ext_dir, fname))
                            except PermissionError:
                                log(f"Skipping copy {fname} (In Use/Permission Denied)", "DEBUG")
                            except Exception as cpy_err:
                                log(f"Failed copy {fname}: {cpy_err}", "WARN")

                copy_tools_from_dir(base_tools)
                copy_tools_from_dir(os.path.join(base_tools, "ext"))

                exe_path = os.path.join(temp_tools, "orbis-pub-cmd.exe")
                
                # Verify orbis-pub-cmd exists
                log(f"orbis-pub-cmd.exe exists: {os.path.exists(exe_path)}", "DEBUG")
                
            except Exception as e:
                log(f"Tools copy error: {e}", "ERROR")
                QMessageBox.critical(self, self.t("backport_error"), f"Failed to prepare tools: {e}")
                return

            if not os.path.exists(exe_path):
                 QMessageBox.critical(self, self.t("backport_error"), self.t("backport_config_err"))
                 return
                 
            # Build command args (Pass to thread)
            tool_paths = {
                "cmd": exe_path, 
                "sfo": os.path.join(temp_tools, "orbis-pub-sfo.exe")
            }
            
            log(f"Backport Tools Ready. SFO Patcher: {os.path.exists(tool_paths['sfo'])}", "DEBUG")
            
            self.lbl_sys.setText("Backporting...")
            threading.Thread(target=self._execute_backport_all, args=(pkg_path, out_dir, target_fws, tool_paths), daemon=True).start()


    def silent_backport(self, pkg_path, target_fw):
        """
        Silently backports a PKG file to a temp directory using the unified core logic.
        Returns the path to the backported PKG or None if failed.
        """
        try:
            # 1. Setup paths
            temp_tools = os.path.join(tempfile.gettempdir(), "storm_tools")
            
            # Use Root Drive for Backports to avoid Path Length issues (Match Manual Logic)
            # FIX: Use script drive, likely C:\. If not writable, fallback to %TEMP%
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                app_path = os.path.abspath(__file__)
            drive_root = os.path.splitdrive(app_path)[0]
            if not drive_root: drive_root = "C:"
            if not drive_root.endswith(os.sep): drive_root += os.sep
            
            # Try Root Temp First
            out_root = os.path.join(drive_root, "STORM_BP_TEMP", "Silent")
            
            # Check write permission / create
            try:
                os.makedirs(out_root, exist_ok=True)
                # Test write
                test_file = os.path.join(out_root, ".test")
                with open(test_file, "w") as f: f.write("test")
                os.remove(test_file)
            except Exception as e:
                log(f"Root Temp unavailable ({e}), falling back to %TEMP%", "WARN")
                out_root = os.path.join(tempfile.gettempdir(), "STORM_BP_TEMP", "Silent")
                os.makedirs(out_root, exist_ok=True)
            
            # 2. Check/Prepare tools
            python_tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
            cmd_path = os.path.join(temp_tools, "orbis-pub-cmd.exe")
            sfo_path = os.path.join(temp_tools, "orbis-pub-sfo.exe")
            
            if not os.path.exists(cmd_path):
                 os.makedirs(temp_tools, exist_ok=True)
                 for f in os.listdir(python_tools_path):
                     src = os.path.join(python_tools_path, f)
                     if os.path.isfile(src) and (f.endswith(".exe") or f.endswith(".dll")):
                         shutil.copy2(src, os.path.join(temp_tools, f))
                 
                 # Copy 'ext' folder if exists (Critical for some PKGs logic)
                 ext_src = os.path.join(python_tools_path, "ext")
                 if os.path.exists(ext_src):
                     ext_dst = os.path.join(temp_tools, "ext")
                     os.makedirs(ext_dst, exist_ok=True)
                     for f in os.listdir(ext_src):
                         src = os.path.join(ext_src, f)
                         if os.path.isfile(src): shutil.copy2(src, os.path.join(ext_dst, f))
            
            tool_paths = {
                "cmd": cmd_path,
                "sfo": sfo_path
            }
            
            if not os.path.exists(cmd_path):
                log("Silent BP: Tools not found", "ERROR")
                return None
                
            # 3. Call Unified Core
            # We use a randomized temp folder to avoid collisions
            work_dir_name = "bp_" + str(random.randint(10000, 99999))
            work_dir = os.path.join(out_root, work_dir_name)
            
            success, out_pkg = self._backport_core(pkg_path, target_fw, work_dir, tool_paths, silent=True)
            
            if success and out_pkg and os.path.exists(out_pkg):
                return out_pkg
            else:
                return None
                
        except Exception as e:
            log(f"Silent BP Handler Failed: {e}", "ERROR")
            return None

    def _execute_backport_all(self, pkg_path, out_dir, fw_versions, tools):
        """Execute backport for all specified firmware versions using unified core."""
        total = len(fw_versions)
        
        # Normalize paths
        pkg_path = os.path.normpath(pkg_path)
        base_out_dir = os.path.normpath(out_dir)
        
        # Root temp logic (preserved from original)
        drive_root = os.path.splitdrive(base_out_dir)[0]
        if not drive_root: 
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                app_path = os.path.abspath(__file__)
            drive_root = os.path.splitdrive(app_path)[0]
        if not drive_root: drive_root = "C:" 
        if not drive_root.endswith(os.sep): drive_root += os.sep
        
        if not drive_root.endswith(os.sep): drive_root += os.sep
        
        # Common temp root
        work_root_base = os.path.join(drive_root, "STORM_BP_TEMP")
        
        # Fallback Logic
        try:
             os.makedirs(work_root_base, exist_ok=True)
             # Test write
             test_file = os.path.join(work_root_base, ".test")
             with open(test_file, "w") as f: f.write("test")
             os.remove(test_file)
        except:
             log("Root Temp unavailable for Manual BP, using %TEMP%", "WARN")
             work_root_base = os.path.join(tempfile.gettempdir(), "STORM_BP_TEMP")
             os.makedirs(work_root_base, exist_ok=True)
             
        if os.path.exists(work_root_base):
            try: 
                 # Only clear if it looks like our temp folder
                 if "STORM_BP_TEMP" in work_root_base:
                     shutil.rmtree(work_root_base)
                     os.makedirs(work_root_base, exist_ok=True)
            except: pass
        else:
             os.makedirs(work_root_base, exist_ok=True)

        for i, fw_ver in enumerate(fw_versions, 1):
            log(f"=== Backport {i}/{total}: {fw_ver} ===", "INFO")
            server_signals.status_msg.emit(f"Backporting {i}/{total}: {fw_ver}")
            
            # Specific work dir for this version
            work_dir = os.path.join(work_root_base, f"work_{fw_ver.replace('.', '')}")
            
            # Core Execution
            success, built_pkg = self._backport_core(pkg_path, fw_ver, work_dir, tools, silent=False)
            
            if success and built_pkg and os.path.exists(built_pkg):
                # Move to final destination
                final_name = os.path.basename(built_pkg).replace("-BP.pkg", f"-{fw_ver}-BP.pkg") # Tag with FW
                final_path = os.path.join(base_out_dir, final_name)
                
                if os.path.exists(final_path): os.remove(final_path)
                shutil.move(built_pkg, final_path)
                log(f"Backport Saved: {final_path}", "INFO")
            else:
                log(f"Backport failed for {fw_ver}", "ERROR")
        
        # Cleanup
        try: shutil.rmtree(work_root_base)
        except: pass
            
        server_signals.status_msg.emit(f"All {total} backports complete!")
        log(f"=== All {total} backports finished! ===", "INFO")

    def _backport_core(self, pkg_path, fw_ver, work_dir, tools, silent=False):
        """
        Unified Backport Logic.
        Returns (success, path_to_pkg)
        """
        try:
            os.makedirs(work_dir, exist_ok=True)
            if not silent: server_signals.status_msg.emit(f"Backporting to {fw_ver}...")
            
            # 1. EXTRACT
            cmd_extract_zeros = f'"{tools["cmd"]}" img_extract --passcode 00000000000000000000000000000000 "{pkg_path}" "{work_dir}"'
            
            log(f"Extracting to {work_dir}...", "INFO")
            
            # Try strict passcode first
            if self._run_bp_cmd(cmd_extract_zeros, custom_cwd=work_dir) != 0:
                log("Standard passcode failed. Retrying generic...", "WARN")
                # Try no passcode (encrypted)
                cmd_extract_nopass = f'"{tools["cmd"]}" img_extract --no_passcode "{pkg_path}" "{work_dir}"'
                self._run_bp_cmd(cmd_extract_nopass, custom_cwd=work_dir)
                
                # Check critical files
                eboot_found = os.path.exists(os.path.join(work_dir, "eboot.bin")) or \
                              os.path.exists(os.path.join(work_dir, "Image0", "eboot.bin")) or \
                              os.path.exists(os.path.join(work_dir, "sc0", "param.sfo")) or \
                              os.path.exists(os.path.join(work_dir, "sce_sys", "param.sfo"))

                if not eboot_found:
                    log("Extraction seems incomplete (passcode needed?).", "WARN")
                    # If silent (auto), we fail.
                    if silent: return False, None
            
            # 2. RESTRUCTURE
            sc0_dir = os.path.join(work_dir, "Sc0")
            sce_sys_dir = os.path.join(work_dir, "sce_sys")
            image0_dir = os.path.join(work_dir, "Image0")
            
            if os.path.exists(sc0_dir) and not os.path.exists(sce_sys_dir):
                os.rename(sc0_dir, sce_sys_dir)
            
            if os.path.exists(image0_dir):
                for item in os.listdir(image0_dir):
                    src = os.path.join(image0_dir, item)
                    dst = os.path.join(work_dir, item)
                    if not os.path.exists(dst): shutil.move(src, dst)
                try: shutil.rmtree(image0_dir)
                except: pass

            # 3. PATCH SFO
            sfo_path = os.path.join(work_dir, "sce_sys", "param.sfo")
            content_id = "IV0000-AAAA00000_00-0000000000000000"
            pkg_category = "gd"
            
            if os.path.exists(sfo_path):
                # Get Content ID
                try:
                    with open(sfo_path, "rb") as f:
                        info = get_pkg_info_from_sfo(f.read())
                        content_id = info.get("CONTENT_ID", content_id)
                except: pass
            
                # Patch Version
                try:
                    parts = fw_ver.split('.')
                    maj = int(parts[0])
                    min_ = int(parts[1]) if len(parts)>1 else 0
                    ver_int = (maj << 24) | (min_ << 16)
                    
                    editor = SFOEditor(file_path=sfo_path)
                    editor.set_int("PUBTOOL_VER", ver_int)
                    editor.set_int("SDK_VER", ver_int)
                    editor.set_int("SYSTEM_VER", ver_int)
                    
                    pkg_category = editor.get("CATEGORY", "gd")
                    # Update Content ID from the actual SFO
                    cid_temp = editor.get("CONTENT_ID", "")
                    if cid_temp and len(cid_temp) == 36:
                        content_id = cid_temp
                        log(f"Detected Content ID: {content_id}", "DEBUG")
                    
                    editor.save()
                    log(f"SFO Patched to {fw_ver} (Category: {pkg_category})", "INFO")
                except Exception as e:
                    log(f"SFO Patch Error: {e}", "ERROR")

            # 4. PATCH ELF
            patcher = ElfPatcher(fw_ver)
            patch_count = 0
            for root, dirs, files in os.walk(work_dir):
                for file in files:
                     if file.lower() in ["eboot.bin"] or file.lower().endswith(".prx"):
                         if patcher.patch_file(os.path.join(root, file)):
                             patch_count += 1
            log(f"ELF Patching Complete. Patched: {patch_count}", "INFO")

            # 5. GENERATE GP4
            gp4_path = os.path.join(work_dir, "project.gp4")
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Determine Volume Type
            vol_type = "pkg_ps4_app"
            if pkg_category.lower().strip().startswith("ac"): vol_type = "pkg_ps4_ac_data"
            elif pkg_category.lower().strip().startswith("gp"): vol_type = "pkg_ps4_patch"
            
            lines = [
                '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
                '<psproject fmt="gp4" version="1000">',
                '  <volume>',
                f'    <volume_type>{vol_type}</volume_type>',
                f'    <volume_id>{content_id}</volume_id>',
                f'    <volume_ts>{ts}</volume_ts>',
                f'    <package content_id="{content_id}" passcode="00000000000000000000000000000000"/>',
                '  </volume>',
                '  <files img_no="0">'
            ]
            
            # Add files to GP4 (Excluding generated system files)
            excluded_files = {"license.dat", "license.info", "psreserved.dat", "project.gp4", "backport.gp4"}
            
            for root, _, files in os.walk(work_dir):
                for f in files:
                    if f.lower() in excluded_files: continue
                    
                    full_path = os.path.join(root, f)
                    if full_path == gp4_path: continue # Redundant but safe
                    
                    # Avoid adding the output pkg itself if it exists
                    if f.endswith(".pkg"): continue
                    
                    rel_path = os.path.relpath(full_path, work_dir).replace("\\", "/")
                    lines.append(f'    <file targ_path="{rel_path}" orig_path="{full_path}"/>')

            lines.append('  </files>')
            lines.append('  <rootdir></rootdir>')
            lines.append('</psproject>')
            
            with open(gp4_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            # 6. BUILD PKG
            out_pkg_name = f"{content_id}-BP.pkg"
            out_pkg_path = os.path.join(work_dir, out_pkg_name)
            
            cmd_build = f'"{tools["cmd"]}" img_create --no_progress_bar "{gp4_path}" "{out_pkg_path}"'
            
            log(f"Building PKG ({vol_type})...", "INFO")
            
            if self._run_bp_cmd(cmd_build, custom_cwd=work_dir) == 0:
                if os.path.exists(out_pkg_path):
                    return True, out_pkg_path
            
            log("Build failed (PKG not created).", "ERROR")
            return False, None

        except Exception as e:
            log(f"Backport Core Error: {e}", "ERROR")
            traceback.print_exc()
            return False, None



        
    def _run_bp_cmd(self, cmd, custom_cwd=None):
        try:
            # Setup ENV with tools in PATH
            env = os.environ.copy()
            # Extract tools dir from command to add to PATH
            tools_dir = os.path.dirname(shlex.split(cmd)[0].strip('"'))
            env["PATH"] = tools_dir + os.pathsep + env.get("PATH", "")
            
            work_dir = custom_cwd if custom_cwd else tools_dir
            
            log(f"Running: {cmd}", "DEBUG")
            log(f"CWD: {work_dir}", "DEBUG")
            
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                 env=env, cwd=work_dir)
            out, err = p.communicate(timeout=1200) # 20 mins
            
            # Log ALL output
            if out:
                for line in out.decode(errors='ignore').splitlines():
                    log(f"STDOUT: {line}", "DEBUG")
            if err:
                for line in err.decode(errors='ignore').splitlines():
                    log(f"STDERR: {line}", "ERROR")
            
            if p.returncode != 0:
                log(f"CMD Failed (code {p.returncode}): {cmd}", "ERROR")
                server_signals.status_msg.emit("Backport Error!")
                return p.returncode
            return 0
        except Exception as e:
            log(f"CMD Exception: {e}", "ERROR")
            return -1

    def check_vc_redist_installed(self):
        """Check if VC++ Redistributable 2015-2022 (x64) is installed."""
        # Only needed on Windows
        if os.name != 'nt': return

        try:
            # Check for x64 Runtime
            key_path = r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
            # Access Registry without forcing 64-bit view (Python x64 sees x64 reg by default)
            # If App is 32-bit, we might need KEY_WOW64_64KEY, but usually WinReg handles this?
            # Safe bet is to try both or rely on default.
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                installed, _ = winreg.QueryValueEx(key, "Installed")
                if installed == 1:
                    log("VC++ Redistributable 2015-2022 (x64) is installed.", "INFO")
                    return
        except OSError:
            pass
            
        log("VC++ Redistributable (x64) NOT found.", "WARN")
        self.prompt_install_vc_redist()

    def prompt_install_vc_redist(self):
        """Ask user to install VC++ Redist."""
        msg = "Для работы бэкпортов и корректной обработки мелких файлов требуется:\n" \
              "Microsoft Visual C++ Redistributable 2015-2022 (x64).\n\n" \
              "Скачать и установить сейчас?"
        if self.settings.value("language", "ru") != "ru":
             msg = "Backports and small file processing require:\n" \
                   "Microsoft Visual C++ Redistributable 2015-2022 (x64).\n\n" \
                   "Download and install now?"
                   
        reply = QMessageBox.question(self, "Visual C++ Runtime Missing", msg, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                     
        if reply == QMessageBox.StandardButton.Yes:
            url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
            save_path = os.path.join(tempfile.gettempdir(), "vc_redist.x64.exe")
            
            try:
                self.show_loading_progress("Downloading VC++ Redist...", 0)
                QApplication.processEvents()
                
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                if hasattr(self, 'loading_progress') and self.loading_progress: 
                    self.loading_progress.close()
                
                log(f"Installing VC++ from {save_path}...", "INFO")
                # /install /passive /norestart
                subprocess.run([save_path, "/install", "/passive", "/norestart"], check=True)
                
                QMessageBox.information(self, "Done", "Visual C++ installed! Please restart the app.")
                
            except Exception as e:
                if hasattr(self, 'loading_progress') and self.loading_progress: 
                    self.loading_progress.close()
                log(f"VC++ Install Error: {e}", "ERROR")
                QMessageBox.critical(self, "Error", f"Failed to install VC++:\n{e}")

def exception_hook(exctype, value, traceback_obj):
    import traceback
    # Print to console/stderr for dev
    traceback.print_exception(exctype, value, traceback_obj)
    try:
        # Append to crash.log
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*30}\n[{datetime.datetime.now()}] CRASH:\n")
            traceback.print_exception(exctype, value, traceback_obj, file=f)
    except: pass
    
    # Try to show message box if possible
    try:
        error_msg = str(value)
        # We can't safely use QMessageBox here if app is crashing, but we can try ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Application Error:\n{error_msg}\n\nSee crash.log for details.", "STORM Fatal Error", 0x10)
    except: pass
    
    sys.exit(1)

if __name__ == "__main__":
    import multiprocessing; multiprocessing.freeze_support()
    sys.excepthook = exception_hook
    app = QApplication(sys.argv)
    ico_path = resource_path("stormps4pkgsender.ico")
    if os.path.exists(ico_path): app_icon = QIcon(ico_path); app.setWindowIcon(app_icon)
    app.setApplicationName("STORM PS4 PKG SENDER")
    app.setStyle("Fusion")
    
    # FIX: Connect cleanup to application exit (Backup for closeEvent)
    # This runs even if window is closed via Taskbar or other means that skip closeEvent
    def app_cleanup():
        try:
             settings = QSettings(myappid, "StormSettings")
             val = settings.value("cleanup_backports", True, type=bool)
             perform_cleanup(val)
        except: pass
    app.aboutToQuit.connect(app_cleanup)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())