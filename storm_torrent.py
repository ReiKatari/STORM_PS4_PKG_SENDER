"""STORM PS4 PKG SENDER - qBittorrent & Torznab Auto-Install Engine.

Provides:
1. QBittorrentClient: Web API v2 integration (auth, torrent management, NAS path translation).
2. TorznabClient: Torrent search integration with Jackett and Prowlarr.
3. TorrentAutoInstallThread: Background watchdog that detects completed torrents,
   scans for .pkg files, and signals MainWindow to auto-queue them for PS4 installation.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any, List, Tuple
import requests

from PyQt6.QtCore import QThread, pyqtSignal


def normalize_slashes(path: str) -> str:
    """Normalize path slashes for consistent comparison."""
    return path.replace("\\", "/").rstrip("/")


def translate_remote_to_local_path(source_path: str, remote_path: str, local_path: str) -> str:
    """Translate a path reported by remote qBittorrent (NAS/Docker) to a local Windows path."""
    if not remote_path or not local_path:
        return source_path

    norm_source = normalize_slashes(source_path)
    norm_remote = normalize_slashes(remote_path)

    if norm_source.lower() == norm_remote.lower():
        return local_path

    if norm_source.lower().startswith(norm_remote.lower() + "/"):
        rel = norm_source[len(norm_remote):].lstrip("/")
        return os.path.normpath(os.path.join(local_path, rel))

    return source_path


class QBittorrentClient:
    """qBittorrent Web API v2 client with support for modern and legacy sessions."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        username: str = "",
        password: str = "",
        local_download_dir: str = "",
        remote_nas_dir: str = "",
        timeout: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.local_download_dir = local_download_dir
        self.remote_nas_dir = remote_nas_dir
        self.timeout = timeout
        self.session = requests.Session()
        self.is_logged_in = False
        self.qbit_version = ""

    def login(self) -> Tuple[bool, str]:
        """Authenticate against qBittorrent Web UI."""
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = f"http://{self.base_url}"

        login_url = f"{self.base_url}/api/v2/auth/login"
        try:
            r = self.session.post(
                login_url,
                data={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )

            # qBittorrent < 5.2 returns 200 "Ok." / "Fails."
            # qBittorrent >= 5.2 returns 204 No Content
            if r.status_code == 403:
                return False, "qBittorrent IP banned temporarily. Wait or restart qBittorrent."
            if r.status_code == 401 or "fails" in r.text.lower():
                return False, "Invalid username or password for qBittorrent Web UI."
            if r.status_code not in (200, 204):
                return False, f"Server returned status {r.status_code}"

            # Verify login by fetching version
            v_res = self.session.get(f"{self.base_url}/api/v2/app/version", timeout=self.timeout)
            if v_res.status_code == 200:
                self.qbit_version = v_res.text.strip()
                self.is_logged_in = True
                return True, f"Connected to qBittorrent {self.qbit_version}"
            return False, "Authentication succeeded but failed to fetch version."

        except Exception as e:
            self.is_logged_in = False
            return False, f"Connection error: {e}"

    def get_torrents(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch list of torrents, optionally filtered by tag."""
        if not self.is_logged_in:
            ok, _ = self.login()
            if not ok:
                return []

        url = f"{self.base_url}/api/v2/torrents/info"
        params = {}
        if tag:
            params["tag"] = tag

        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 403:
                # Re-login once
                if self.login()[0]:
                    r2 = self.session.get(url, params=params, timeout=self.timeout)
                    if r2.status_code == 200:
                        return r2.json()
        except Exception:
            pass
        return []

    def add_torrent(self, source: str, auto_install: bool = True) -> Tuple[bool, str]:
        """Add a magnet link or HTTP(S) torrent URL."""
        if not self.is_logged_in:
            ok, msg = self.login()
            if not ok:
                return False, msg

        tags = "storm-pkg"
        if auto_install:
            tags += ",storm-auto-install"

        data: Dict[str, Any] = {
            "urls": source,
            "tags": tags,
        }
        if self.remote_nas_dir:
            data["savepath"] = self.remote_nas_dir
        elif self.local_download_dir:
            data["savepath"] = self.local_download_dir

        try:
            r = self.session.post(f"{self.base_url}/api/v2/torrents/add", data=data, timeout=self.timeout)
            if r.status_code == 200 and "fails" not in r.text.lower():
                return True, "Torrent added successfully"
            return False, f"qBittorrent rejected torrent: {r.text}"
        except Exception as e:
            return False, str(e)

    def pause_torrent(self, torrent_hash: str) -> bool:
        """Pause a torrent."""
        try:
            r = self.session.post(f"{self.base_url}/api/v2/torrents/pause", data={"hashes": torrent_hash}, timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def resume_torrent(self, torrent_hash: str) -> bool:
        """Resume a torrent."""
        try:
            r = self.session.post(f"{self.base_url}/api/v2/torrents/resume", data={"hashes": torrent_hash}, timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """Delete a torrent, optionally keeping files."""
        try:
            r = self.session.post(
                f"{self.base_url}/api/v2/torrents/delete",
                data={"hashes": torrent_hash, "deleteFiles": str(delete_files).lower()},
                timeout=self.timeout,
            )
            return r.status_code == 200
        except Exception:
            return False

    def find_pkgs_for_torrent(self, torrent: Dict[str, Any]) -> List[str]:
        """Find local .pkg files corresponding to a completed torrent."""
        content_path = torrent.get("content_path", "")
        save_path = torrent.get("save_path", "")

        target = content_path or save_path
        if not target:
            return []

        local_target = translate_remote_to_local_path(target, self.remote_nas_dir, self.local_download_dir)

        pkg_files: List[str] = []
        if os.path.isfile(local_target) and local_target.lower().endswith(".pkg"):
            pkg_files.append(os.path.normpath(local_target))
        elif os.path.isdir(local_target):
            for root, _, files in os.walk(local_target):
                for f in files:
                    if f.lower().endswith(".pkg"):
                        pkg_files.append(os.path.normpath(os.path.join(root, f)))

        return sorted(pkg_files)


class TorznabClient:
    """Torznab API search client (compatible with Jackett & Prowlarr)."""

    def __init__(self, base_url: str = "", api_key: str = "", timeout: float = 6.0):
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        self.timeout = timeout

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform search and return parsed list of torrent items."""
        if not self.base_url:
            return []

        url = self.base_url
        params = {
            "t": "search",
            "q": query,
            "apikey": self.api_key,
        }

        results: List[Dict[str, Any]] = []
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
            if r.status_code != 200:
                return []

            root = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                size_str = item.findtext("size", "0")
                size = int(size_str) if size_str.isdigit() else 0

                enclosure = item.find("enclosure")
                download_url = enclosure.get("url", "") if enclosure is not None else link

                seeds = 0
                peers = 0
                for attr in item.findall("{http://torznab.com/schemas/2015/feed}attr"):
                    name = attr.get("name")
                    val = attr.get("value", "0")
                    if name == "seeders" and val.isdigit():
                        seeds = int(val)
                    elif name == "peers" and val.isdigit():
                        peers = int(val)

                results.append({
                    "title": title,
                    "size_bytes": size,
                    "size_gb": round(size / (1024 ** 3), 2),
                    "seeds": seeds,
                    "peers": peers,
                    "download_url": download_url,
                })

        except Exception:
            pass

        return results


class TorrentAutoInstallWatcher(QThread):
    """Background watcher that monitors qBittorrent and triggers auto-installation."""

    torrents_updated = pyqtSignal(list)
    auto_install_triggered = pyqtSignal(str, list)  # torrent_name, list_of_pkg_paths
    status_updated = pyqtSignal(str, bool)  # message, is_connected

    def __init__(self, get_client_func, parent=None):
        super().__init__(parent)
        self.get_client = get_client_func
        self._running = True
        self._processed_hashes = set()

    def run(self):
        while self._running:
            client = self.get_client()
            if client and client.base_url:
                try:
                    torrents = client.get_torrents()
                    self.status_updated.emit(f"qBittorrent: {client.qbit_version or 'Connected'}", True)
                    self.torrents_updated.emit(torrents)

                    # Check for completed torrents with storm-auto-install
                    for t in torrents:
                        h = t.get("hash", "")
                        progress = t.get("progress", 0)
                        state = t.get("state", "").lower()
                        tags = [x.strip() for x in t.get("tags", "").split(",")]

                        # Completed states: uploading, pausedUP, completed, stalledUP
                        is_finished = progress >= 0.999 or "upload" in state or "complete" in state or state == "pausedup"

                        if is_finished and "storm-auto-install" in tags:
                            if h not in self._processed_hashes:
                                self._processed_hashes.add(h)
                                pkgs = client.find_pkgs_for_torrent(t)
                                if pkgs:
                                    self.auto_install_triggered.emit(t.get("name", "Torrent"), pkgs)

                except Exception as e:
                    self.status_updated.emit(f"qBittorrent: Disconnected ({e})", False)
            else:
                self.status_updated.emit("qBittorrent: Not Configured", False)

            # Sleep 3 seconds
            for _ in range(6):
                if not self._running:
                    break
                time.sleep(0.5)

    def stop(self):
        self._running = False
        self.wait(1500)
