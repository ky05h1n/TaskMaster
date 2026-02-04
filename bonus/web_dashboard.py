import json
import os
import socket
from typing import Dict, Any, List, Optional

import psutil
from flask import Flask, jsonify, request

app = Flask(__name__)

HOST = "127.0.0.1"
PORT = 8765
SOCKET_PATH = os.environ.get("TASKMASTER_SOCKET", "/tmp/taskmaster.sock")


@app.route("/")
def index() -> str:
        return """
<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>TaskMaster Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 24px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            th { background: #f5f5f5; }
            .running { color: #0a7a0a; font-weight: bold; }
            .stopped { color: #b00020; font-weight: bold; }
            .attached { color: #1f7a8c; font-weight: bold; }
            .detached { color: #777; font-weight: bold; }
            button { margin-right: 6px; }
        </style>
    </head>
    <body>
        <h1>TaskMaster Dashboard</h1>
        <div id="status" style="margin: 8px 0; color: #b00020;"></div>
        <table>
            <thead>
                <tr>
                    <th>Program</th>
                    <th>PID</th>
                      <th>Status</th>
                      <th>Attached</th>
                    <th>CPU %</th>
                    <th>Memory MB</th>
                    <th>Command</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id=\"rows\"></tbody>
        </table>

        <script>
            async function fetchStatus() {
                const res = await fetch('/api/status');
                const payload = await res.json();
                const statusEl = document.getElementById('status');
                const data = payload.data ?? [];
                if (!payload.ok) {
                    statusEl.textContent = payload.message || 'Cannot connect to daemon.';
                } else {
                    statusEl.textContent = '';
                }
                const tbody = document.getElementById('rows');
                tbody.innerHTML = '';
                data.forEach(item => {
                    const tr = document.createElement('tr');
                    const statusClass = item.status === 'STARTED' ? 'running' : 'stopped';
                    tr.innerHTML = `
                        <td>${item.name}</td>
                        <td>${item.pid ?? '-'}</td>
                        <td class=\"${statusClass}\">${item.status}</td>
                        <td class="${item.attached ? 'attached' : 'detached'}">${item.attached ? 'ATTACHED' : 'DETACHED'}</td>
                        <td>${item.cpu ?? '-'}</td>
                        <td>${item.mem ?? '-'}</td>
                        <td>${item.cmd}</td>
                        <td>
                            <button onclick=\"sendAction('start','${item.name}')\">Start</button>
                            <button onclick=\"sendAction('stop','${item.name}')\">Stop</button>
                            <button onclick=\"sendAction('restart','${item.name}')\">Restart</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            async function sendAction(action, name) {
                await fetch(`/api/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target: name })
                });
                fetchStatus();
            }

            fetchStatus();
            setInterval(fetchStatus, 2000);
        </script>
    </body>
</html>
        """


@app.route("/api/status")
def api_status():
    try:
        status = _send_command("status")
    except Exception as exc:
        return jsonify({"ok": False, "message": f"Error: {exc}", "data": []})
    if not status.get("ok"):
        return jsonify({"ok": False, "message": status.get("message", "No response"), "data": []})
    rows: List[Dict[str, Any]] = []
    for entry in status.get("data", []):
        pid = entry.get("pid")
        cpu = None
        mem = None
        if pid:
            try:
                p = psutil.Process(pid)
                cpu = round(p.cpu_percent(interval=0.0), 1)
                mem = round(p.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                cpu = None
                mem = None
        rows.append({
            "name": entry.get("name"),
            "pid": pid,
            "status": entry.get("status"),
            "cmd": entry.get("cmd"),
            "attached": entry.get("attached", False),
            "cpu": cpu,
            "mem": mem,
        })
    return jsonify({"ok": True, "data": rows})


@app.route("/api/start", methods=["POST"])
def api_start():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target")
    if not target:
        return jsonify({"ok": False, "message": "No program specified"}), 400
    result = _send_command("start", target)
    return jsonify(result)


@app.route("/api/stop", methods=["POST"])
def api_stop():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target")
    if not target:
        return jsonify({"ok": False, "message": "No program specified"}), 400
    result = _send_command("stop", target)
    return jsonify(result)


@app.route("/api/restart", methods=["POST"])
def api_restart():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target")
    if not target:
        return jsonify({"ok": False, "message": "No program specified"}), 400
    result = _send_command("restart", target)
    return jsonify(result)


def _open_socket() -> socket.socket:
    if os.name == "nt":
        return socket.create_connection((HOST, PORT))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    return sock


def _read_line(sock: socket.socket) -> Optional[Dict[str, Any]]:
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(1)
        if not chunk:
            return None
        data += chunk
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _send_command(cmd: str, target: Optional[str] = None) -> Dict[str, Any]:
    try:
        sock = _open_socket()
    except OSError as exc:
        return {"ok": False, "message": f"Cannot connect to daemon: {exc}"}
    try:
        payload = {"cmd": cmd, "target": target}
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        response = _read_line(sock)
        return response or {"ok": False, "message": "No response"}
    except OSError as exc:
        return {"ok": False, "message": f"Socket error: {exc}"}
    finally:
        sock.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
