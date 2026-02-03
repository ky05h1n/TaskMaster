import json
import os
import socket
import sys
import threading
import time
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from TaskMaster import TaskMaster, CONFILE


HOST = "127.0.0.1"
PORT = 8765


class TaskMasterServer:
    def __init__(self, config_file: str = CONFILE):
        self.taskmaster = TaskMaster(config_file)
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.listener: Optional[socket.socket] = None

    def start(self) -> None:
        self.taskmaster.Load_config()
        self.taskmaster.Run()

        monitor_thread = threading.Thread(target=self.taskmaster.Monitor, daemon=True)
        monitor_thread.start()

        self._serve()

    def _serve(self) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((HOST, PORT))
        self.listener.listen(5)

        while not self.shutdown_event.is_set():
            try:
                self.listener.settimeout(1.0)
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
            thread.start()

        if self.listener:
            try:
                self.listener.close()
            except OSError:
                pass

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            reader = client.makefile("r", encoding="utf-8")
            writer = client.makefile("w", encoding="utf-8")
            for line in reader:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    response = self._dispatch(payload)
                except json.JSONDecodeError:
                    response = {"ok": False, "message": "Invalid JSON"}
                except Exception as exc:
                    response = {"ok": False, "message": f"Server error: {exc}"}

                writer.write(json.dumps(response) + "\n")
                writer.flush()

                if response.get("shutdown"):
                    break

    def _dispatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cmd = payload.get("cmd")
        target = payload.get("target")

        if cmd == "status":
            return self._status()
        if cmd == "start":
            return self._start(target)
        if cmd == "stop":
            return self._stop(target)
        if cmd == "restart":
            return self._restart(target)
        if cmd == "reload":
            return self._reload()
        if cmd in ("quit", "exit"):
            self.shutdown_event.set()
            if self.listener:
                try:
                    self.listener.close()
                except OSError:
                    pass
            return {"ok": True, "message": "Taskmaster server shutting down", "shutdown": True}

        return {"ok": False, "message": f"Unknown command: {cmd}"}

    def _status(self) -> Dict[str, Any]:
        with self.lock:
            programs = []
            for prog in list(self.taskmaster.programs.keys()):
                proc, items = self.taskmaster.programs[prog]
                status = items.get("status")
                cmd = items.get("cmd", "N/A")
                pid = proc.pid if proc else None
                programs.append({
                    "name": prog,
                    "pid": pid,
                    "status": status,
                    "cmd": cmd,
                })

        return {"ok": True, "message": "Status retrieved", "data": programs}

    def _start(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {"ok": False, "message": "No program specified"}

        with self.lock:
            if target not in self.taskmaster.programs:
                return {"ok": False, "message": f"Program '{target}' not found"}
            proc, items = self.taskmaster.programs[target]
            if items.get("status") == "STARTED":
                return {"ok": False, "message": f"Program '{target}' is already running"}

            items["sig"] = "START"
            self.taskmaster.Run({target: items})
            items["sig"] = None

        return {"ok": True, "message": f"Program '{target}' started"}

    def _stop(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {"ok": False, "message": "No program specified"}

        with self.lock:
            if target not in self.taskmaster.programs:
                return {"ok": False, "message": f"Program '{target}' not found"}
            proc, items = self.taskmaster.programs[target]
            if items.get("status") != "STARTED" or proc is None:
                return {"ok": False, "message": f"Program '{target}' is not running"}

            proc.terminate()
            items["status"] = "STOPPED"
            self.taskmaster.log_info("Stopped", target, proc.pid)

        return {"ok": True, "message": f"Program '{target}' stopped"}

    def _restart(self, target: Optional[str]) -> Dict[str, Any]:
        stop_resp = self._stop(target)
        if not stop_resp.get("ok"):
            return stop_resp
        time.sleep(1)
        start_resp = self._start(target)
        if start_resp.get("ok"):
            self.taskmaster.log_info("Restarted", target)
        return start_resp

    def _reload(self) -> Dict[str, Any]:
        with self.lock:
            new_conf = self.taskmaster.Load_config("reload")
            changed = False

            for prog_new, items_new in new_conf.items():
                if prog_new not in self.taskmaster.programs:
                    items_new["status"] = "CREATED"
                    items_new["sig"] = None
                    self.taskmaster.programs[prog_new] = (None, items_new)
                    changed = True
                else:
                    proc, items = self.taskmaster.programs[prog_new]
                    save = items.pop("status", None)
                    items.pop("sig", None)
                    items_new.pop("status", None)
                    items_new.pop("sig", None)
                    if items_new != items:
                        items_new["status"] = "CREATED"
                        items_new["sig"] = None
                        if proc is not None:
                            proc.terminate()
                        proc = None
                        self.taskmaster.programs[prog_new] = (proc, items_new)
                        self.taskmaster.Run({prog_new: items_new})
                        changed = True
                    else:
                        items["status"] = save
                        items["sig"] = None
                        self.taskmaster.programs[prog_new] = (proc, items)

            for prog in list(self.taskmaster.programs.keys()):
                if prog not in new_conf:
                    proc, _ = self.taskmaster.programs[prog]
                    if proc is not None:
                        proc.terminate()
                    self.taskmaster.programs.pop(prog)
                    changed = True

            self.taskmaster.log_info("Configuration Reloaded")

        if changed:
            return {"ok": True, "message": "Configuration reloaded"}
        return {"ok": True, "message": "Configuration reloaded, nothing changed"}


def main() -> None:
    server = TaskMasterServer(CONFILE)
    server.start()


if __name__ == "__main__":
    main()
