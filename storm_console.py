"""STORM PS4 PKG SENDER - Console Companion Service Client.

Connects to PackegeFlowService / Console REST API on port 12801 for:
1. System hardware info, firmware, model family, GoldHEN status.
2. Storage disk volume analysis (Internal HDD and External USB storage).
3. Live installed apps and DLCs catalog on the PS4.
4. Component-level safe uninstallation (removing an individual DLC or patch without touching saves).
"""

import uuid
import requests
from typing import Optional, Dict, Any, List, Tuple


class PackegeFlowServiceClient:
    """Client for PS4 Console Companion Service (PackegeFlowService, Port 12801)."""

    def __init__(self, ps4_ip: str, port: int = 12801, timeout: float = 4.0):
        self.ps4_ip = ps4_ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{ps4_ip}:{port}"
        self.paired_key: Optional[str] = None

    def ping(self) -> Tuple[bool, str]:
        """Check if PackegeFlowService is running on the console."""
        try:
            r = requests.get(f"{self.base_url}/ping", timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                if data.get("service") == "PackegeFlowService":
                    return True, data.get("version", "unknown")
            return False, f"Unexpected response: {r.status_code}"
        except Exception as e:
            return False, str(e)

    def get_system_snapshot(self) -> Dict[str, Any]:
        """Fetch comprehensive system, hardware, and storage information."""
        result: Dict[str, Any] = {
            "online": False,
            "version": "",
            "firmware": "",
            "model": "",
            "family": "",
            "hen": "",
            "hen_version": "",
            "storage": [],
            "error": "",
        }

        # 1. Ping
        alive, ver = self.ping()
        if not alive:
            result["error"] = ver
            return result

        result["online"] = True
        result["version"] = ver

        # 2. System info
        try:
            r = requests.get(f"{self.base_url}/system/info", timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                fw = data.get("firmware", {})
                result["firmware"] = fw.get("version", "")
                model = data.get("model", {})
                result["model"] = model.get("name", "")
                result["family"] = model.get("family", "")
                hen = data.get("hen", {})
                result["hen"] = hen.get("name", "")
                result["hen_version"] = hen.get("version", "")
        except Exception:
            pass

        # 3. Storage
        try:
            r = requests.get(f"{self.base_url}/storage", timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                volumes = data.get("volumes", [])
                for vol in volumes:
                    if vol.get("available"):
                        tot = vol.get("totalBytes", 0)
                        free = vol.get("freeBytes", 0)
                        used = vol.get("usedBytes", 0)
                        result["storage"].append({
                            "id": vol.get("id", ""),
                            "path": vol.get("path", ""),
                            "total_gb": round(tot / (1024 ** 3), 1),
                            "free_gb": round(free / (1024 ** 3), 1),
                            "used_gb": round(used / (1024 ** 3), 1),
                            "pct_used": round((used / tot * 100), 1) if tot > 0 else 0,
                        })
        except Exception:
            pass

        return result

    def get_installed_apps(self) -> List[Dict[str, Any]]:
        """Fetch all installed applications from the console."""
        apps: List[Dict[str, Any]] = []
        offset = 0
        revision = ""

        try:
            while True:
                url = f"{self.base_url}/apps/list?offset={offset}"
                if revision:
                    url += f"&revision={revision}"
                r = requests.get(url, timeout=self.timeout)
                if r.status_code != 200:
                    break
                data = r.json()
                revision = data.get("revision", "")
                batch = data.get("apps", [])
                for item in batch:
                    apps.append(item)
                next_offset = data.get("next")
                if next_offset is None or next_offset == offset:
                    break
                offset = next_offset
        except Exception:
            pass

        return apps

    def get_app_details(self, title_id: str) -> Optional[Dict[str, Any]]:
        """Fetch details and components (base, patch, DLCs) for a given TITLE_ID."""
        try:
            offset = 0
            revision = ""
            details: Optional[Dict[str, Any]] = None

            while True:
                url = f"{self.base_url}/apps/title/{title_id}?offset={offset}"
                if revision:
                    url += f"&revision={revision}"
                r = requests.get(url, timeout=self.timeout)
                if r.status_code != 200:
                    break
                data = r.json()
                revision = data.get("revision", "")

                if details is None:
                    details = {
                        "app": data.get("app", {}),
                        "revision": revision,
                        "components": [],
                    }

                for comp in data.get("components", []):
                    details["components"].append(comp)

                next_offset = data.get("next")
                if next_offset is None or next_offset == offset:
                    break
                offset = next_offset

            return details
        except Exception:
            return None

    def remove_component(
        self,
        title_id: str,
        kind: str,
        component_id: str,
        revision: str,
    ) -> Dict[str, Any]:
        """Request removal of a specific component (game, patch, dlc, dlcs)."""
        req_id = str(uuid.uuid4())
        payload = {
            "requestId": req_id,
            "titleId": title_id,
            "kind": kind,
            "componentId": component_id,
            "revision": revision,
            "confirmTitleId": title_id,
        }

        try:
            r = requests.post(f"{self.base_url}/apps/remove", json=payload, timeout=self.timeout)
            if r.status_code in (200, 202):
                return r.json()
            return {"error": f"Server returned {r.status_code}: {r.text}"}
        except Exception as e:
            return {"error": str(e)}

    def check_operation_status(self, request_id: str) -> Dict[str, Any]:
        """Check status of an ongoing removal operation."""
        try:
            r = requests.get(f"{self.base_url}/apps/operations/{request_id}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
            return {"error": f"Status {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}
