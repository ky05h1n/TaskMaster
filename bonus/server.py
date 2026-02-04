import json
import os
import socket
import sys
import threading
import select
import time
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from TaskMaster import CONFILE
from bonus.taskmaster_bonus import BonusTaskMaster


HOST = "127.0.0.1"
PORT = 8765
SOCKET_PATH = "/tmp/taskmaster.sock"


class TaskMasterServer:
    def __init__(self, config_file: str = CONFILE):
        self.taskmaster = BonusTaskMaster(config_file)
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.listener: Optional[socket.socket] = None
        self.attach_counts: Dict[str, int] = {}
        self.attached_targets = set()
        self.attach_clients: Dict[str, set[socket.socket]] = {}

    def start(self) -> None:
        self.taskmaster.Load_config()
        self.taskmaster.Run()

        monitor_thread = threading.Thread(target=self.taskmaster.Monitor, daemon=True)
        monitor_thread.start()

        self._serve()

    def _serve(self) -> None:
        if os.name == "nt":
            self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind((HOST, PORT))
            self.listener.listen(5)
        else:
            if os.path.exists(SOCKET_PATH):
                try:
                    os.remove(SOCKET_PATH)
                except OSError:
                    pass
            self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.listener.bind(SOCKET_PATH)
            os.chmod(SOCKET_PATH, 0o600)
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
        if os.name != "nt" and os.path.exists(SOCKET_PATH):
            try:
                os.remove(SOCKET_PATH)
            except OSError:
                pass

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            if os.name != "nt" and client.family == socket.AF_UNIX:
                peer_cred = getattr(socket, "SO_PEERCRED", None)
                if peer_cred is not None:
                    try:
                        creds = client.getsockopt(socket.SOL_SOCKET, peer_cred, 12)
                        _pid = int.from_bytes(creds[0:4], "little")
                        uid = int.from_bytes(creds[4:8], "little")
                        _gid = int.from_bytes(creds[8:12], "little")
                        if uid != 0:
                            writer = client.makefile("w", encoding="utf-8")
                            writer.write(json.dumps({"ok": False, "message": "Unauthorized (root only)"}) + "\n")
                            writer.flush()
                            return
                    except OSError:
                        writer = client.makefile("w", encoding="utf-8")
                        writer.write(json.dumps({"ok": False, "message": "Unauthorized (root only)"}) + "\n")
                        writer.flush()
                        return
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

                if response.get("attach"):
                    target = response.get("target")
                    master_fd = None
                    if target and target in self.taskmaster.programs:
                            items = self.taskmaster.programs[target]
                            master_fd = items.get("pty_master")
                    if isinstance(master_fd, int):
                        self._register_attach_client(target, client)
                        self._stream_console(client, master_fd, target)
                    break

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
        if cmd == "attach":
            return self._attach(target)
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
                items = self.taskmaster.programs[prog]
                status = items.get("status")
                if status == "CREATED":
                    status = "STOPPED"
                cmd = items.get("cmd", "N/A")
                procs = items.get("procs", [])
                running = [p for p in procs if p.get("proc") and p["proc"].poll() is None]
                pid = running[0]["proc"].pid if running else None
                attached = prog in self.attached_targets
                if not attached:
                    attached = bool(items.get("attached", False))
                items["attached"] = attached
                programs.append({
                    "name": prog,
                    "pid": pid,
                    "status": status,
                    "cmd": cmd,
                    "attached": attached,
                    "attached_count": self.attach_counts.get(prog, 0),
                })

        return {"ok": True, "message": "Status retrieved", "data": programs}

    def _start(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {"ok": False, "message": "No program specified"}

        with self.lock:
            if target not in self.taskmaster.programs:
                return {"ok": False, "message": f"Program '{target}' not found"}
            items = self.taskmaster.programs[target]
            if items.get("status") == "STARTED":
                return {"ok": False, "message": f"Program '{target}' is already running"}

        self.taskmaster.start_program(target)

        with self.lock:
            items = self.taskmaster.programs[target]
            if items.get("status") != "STARTED":
                return {"ok": False, "message": f"Failed to start '{target}'"}

        return {"ok": True, "message": f"Program '{target}' started"}

    def _stop(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {"ok": False, "message": "No program specified"}
        with self.lock:
            if target not in self.taskmaster.programs:
                return {"ok": False, "message": f"Program '{target}' not found"}
            items = self.taskmaster.programs[target]
            if items.get("status") != "STARTED":
                return {"ok": False, "message": f"Program '{target}' is not running"}

        self.taskmaster.stop_program(target)
        with self.lock:
            if target in self.taskmaster.programs:
                items = self.taskmaster.programs[target]
                items["attached"] = False
        self.attach_counts.pop(target, None)
        self.attached_targets.discard(target)
        self._close_attach_clients(target)

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

    def _attach(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {"ok": False, "message": "No program specified"}

        with self.lock:
            if target not in self.taskmaster.programs:
                return {"ok": False, "message": f"Program '{target}' not found"}
            items = self.taskmaster.programs[target]
            if items.get("status") != "STARTED":
                return {"ok": False, "message": f"Program '{target}' is not running"}
            if not isinstance(items.get("pty_master"), int):
                return {"ok": False, "message": f"Program '{target}' has no console"}

        with self.lock:
            self.attach_counts[target] = self.attach_counts.get(target, 0) + 1
            self.attached_targets.add(target)
            if target in self.taskmaster.programs:
                items = self.taskmaster.programs[target]
                items["attached"] = True
        # print(f"[attach] target={target} count={self.attach_counts.get(target)}")
        return {"ok": True, "message": f"Attached to '{target}'. Detach with Ctrl-]", "attach": True, "target": target}

    def _stream_console(self, client: socket.socket, master_fd: int, target: Optional[str]) -> None:
        try:
            client.setblocking(False)
        except OSError:
            return

        while True:
            try:
                rlist, _, _ = select.select([client, master_fd], [], [])
            except OSError:
                break

            if client in rlist:
                try:
                    data = client.recv(1024)
                except OSError:
                    break
                if not data:
                    break
                if b"\x1d" in data:
                    break
                try:
                    os.write(master_fd, data)
                except OSError:
                    break

            if master_fd in rlist:
                try:
                    output = os.read(master_fd, 1024)
                except OSError:
                    break
                if not output:
                    break
                try:
                    client.sendall(output)
                except OSError:
                    break

        if target:
            with self.lock:
                count = self.attach_counts.get(target, 0)
                if count <= 1:
                    self.attach_counts.pop(target, None)
                else:
                    self.attach_counts[target] = count - 1
                self.attached_targets.discard(target)
                if target in self.taskmaster.programs:
                    items = self.taskmaster.programs[target]
                    items["attached"] = self.attach_counts.get(target, 0) > 0
            # print(f"[detach] target={target} count={self.attach_counts.get(target, 0)}")

        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client.close()
        except OSError:
            pass
        if target:
            self._unregister_attach_client(target, client)

    def _register_attach_client(self, target: Optional[str], client: socket.socket) -> None:
        if not target:
            return
        with self.lock:
            clients = self.attach_clients.setdefault(target, set())
            clients.add(client)

    def _unregister_attach_client(self, target: Optional[str], client: socket.socket) -> None:
        if not target:
            return
        with self.lock:
            clients = self.attach_clients.get(target)
            if not clients:
                return
            clients.discard(client)
            if not clients:
                self.attach_clients.pop(target, None)

    def _close_attach_clients(self, target: Optional[str]) -> None:
        if not target:
            return
        with self.lock:
            clients = list(self.attach_clients.get(target, set()))
            self.attach_clients.pop(target, None)
        for sock in clients:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _reload(self) -> Dict[str, Any]:
        changed = self.taskmaster.reload_config()
        if changed:
            return {"ok": True, "message": "Configuration reloaded"}
        return {"ok": True, "message": "Configuration reloaded, nothing changed"}


def _drop_privileges_on_launch() -> None:
    if os.name == "nt":
        return
    if os.geteuid() != 0:
        return

    run_as_user = os.environ.get("TASKMASTER_RUN_AS_USER")
    run_as_group = os.environ.get("TASKMASTER_RUN_AS_GROUP")

    if not run_as_user:
        return

    import grp
    import pwd

    pw = pwd.getpwnam(run_as_user)
    uid = pw.pw_uid
    gid = pw.pw_gid

    if run_as_group:
        gid = grp.getgrnam(run_as_group).gr_gid

    os.initgroups(run_as_user, gid)
    os.setgid(gid)
    os.setuid(uid)


def main() -> None:
    _drop_privileges_on_launch()
    server = TaskMasterServer(CONFILE)
    server.start()


if __name__ == "__main__":
    main()
