import json
import logging
import os
import smtplib
import time
import pty
import urllib.request
import subprocess
import shlex
from datetime import datetime
from email.message import EmailMessage
from logging.handlers import SysLogHandler

import yaml

from TaskMaster import TaskMaster, LOGFILE, GREEN, RED, YELLOW, CYAN, RESET

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class BonusTaskMaster(TaskMaster):
    def __init__(self, configfile):
        super().__init__(configfile)
        self.alerts = {}

    def log_info(self, message, prog=None, pid=None, instance=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if message == "Started":
            symbol = "▶"
        elif message == "Stopped":
            symbol = "▪"
        elif message in ("Restarting", "Restarted"):
            symbol = "↻"
        elif message == "Failed":
            symbol = "✖"
        else:
            symbol = "↻"

        if prog and pid:
            name = f"{prog}:{instance}" if instance is not None else prog
            log_line = f"{symbol} [{timestamp}] [{name}] [PID:{pid}] {message}"
        elif prog:
            name = f"{prog}:{instance}" if instance is not None else prog
            log_line = f"{symbol} [{timestamp}] [{name}] {message}"
        else:
            log_line = f"{symbol} [{timestamp}] {message}"
        with open(LOGFILE, "a", encoding="utf-8") as log_file:
            log_file.write(f"{log_line}\n")
            time.sleep(0.5)
        self._send_alerts(log_line)

    def Load_config(self, state=None):
        self._load_env_file(os.path.join(_BASE_DIR, ".env"))
        with open(self.configfile, "r") as file:
            data = yaml.safe_load(file)
        data = self._expand_env_vars(data)
        programs = data.get("programs", {})
        normalized = {}
        for prog, item in programs.items():
            normalized[prog] = self._normalize_program_config(prog, item)
        if state == "reload":
            return normalized
        self.configdata = normalized
        self.programs = {prog: dict(item) for prog, item in normalized.items()}
        self.alerts = data.get("alerts", {}) or {}

    def _start_process(self, prog, item, index):
        cmd = item.get("cmd", "")
        argv = shlex.split(cmd)
        env = self._build_env(item)
        cwd = item.get("workingdir")
        umask_value = item.get("umask")

        stdout_handle = self._open_output(item.get("stdout"))
        stderr_handle = self._open_output(item.get("stderr"))

        preexec_fn = self._build_preexec_fn(item)

        def _apply_umask():
            if umask_value is not None:
                os.umask(umask_value)
            if preexec_fn:
                preexec_fn()

        use_console = bool(item.get("console"))
        if use_console:
            master_fd, slave_fd = pty.openpty()
            proc = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                preexec_fn=_apply_umask if (umask_value is not None or preexec_fn) else None,
                close_fds=True,
            )
            os.close(slave_fd)
            item["pty_master"] = master_fd
            stdout_handle = subprocess.DEVNULL
            stderr_handle = subprocess.DEVNULL
        else:
            proc = subprocess.Popen(
                argv,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
                cwd=cwd,
                preexec_fn=_apply_umask if (umask_value is not None or preexec_fn) else None,
            )

        proc_info = {
            "proc": proc,
            "start_time": time.time(),
            "retries": 0,
            "stdout_handle": stdout_handle,
            "stderr_handle": stderr_handle,
            "index": index,
        }
        return proc_info

    def stop_program(self, prog):
        super().stop_program(prog)
        item = self.programs.get(prog)
        if not item:
            return
        master_fd = item.get("pty_master")
        if isinstance(master_fd, int):
            try:
                os.close(master_fd)
            except OSError:
                pass
            item.pop("pty_master", None)

    def Monitor(self):
        while True:
            for prog in list(self.programs.keys()):
                item = self.programs[prog]
                procs = list(item.get("procs", []))

                for proc_info in list(procs):
                    proc = proc_info.get("proc")
                    if proc is None:
                        continue
                    ret = proc.poll()
                    if ret is None:
                        continue

                    run_time = time.time() - proc_info.get("start_time", time.time())
                    expected = ret in item.get("exitcodes", [0])
                    autorestart = item.get("autorestart")

                    should_restart = False
                    if autorestart is True:
                        should_restart = True
                    elif isinstance(autorestart, str) and autorestart.lower() == "unexpected":
                        should_restart = not expected

                    if run_time < item.get("starttime", 0):
                        proc_info["retries"] += 1
                        if proc_info["retries"] <= item.get("startretries", 0):
                            should_restart = True
                        else:
                            should_restart = False
                            self.log_info("Failed", prog, proc.pid, instance=proc_info.get("index"))
                    elif should_restart and item.get("startretries", 0) > 0:
                        proc_info["retries"] += 1
                        if proc_info["retries"] > item.get("startretries", 0):
                            should_restart = False
                            self.log_info("Failed", prog, proc.pid, instance=proc_info.get("index"))

                    self._close_output_handles(proc_info)

                    if should_restart:
                        self.log_info("Restarting", prog, proc.pid, instance=proc_info.get("index"))
                        new_proc_info = self._start_process(prog, item, proc_info.get("index", 1))
                        new_proc_info["retries"] = proc_info.get("retries", 0)
                        procs[procs.index(proc_info)] = new_proc_info
                        self.log_info("Started", prog, new_proc_info["proc"].pid, instance=new_proc_info.get("index"))
                    else:
                        self.log_info("Stopped", prog, proc.pid, instance=proc_info.get("index"))
                        procs.remove(proc_info)

                item["procs"] = procs
                self._update_program_status(item)
                if item.get("status") != "STARTED":
                    master_fd = item.get("pty_master")
                    if isinstance(master_fd, int):
                        try:
                            os.close(master_fd)
                        except OSError:
                            pass
                        item.pop("pty_master", None)

            time.sleep(5)

    def _load_env_file(self, env_path: str) -> None:
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as env_file:
                for line in env_file:
                    raw = line.strip()
                    if not raw or raw.startswith("#") or "=" not in raw:
                        continue
                    key, value = raw.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            return

    def _expand_env_vars(self, data):
        if isinstance(data, dict):
            return {key: self._expand_env_vars(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        if isinstance(data, str):
            return os.path.expandvars(data)
        return data

    def _send_alerts(self, log_line: str) -> None:
        alerts = self.alerts or {}
        if not alerts:
            return

        self._send_email_alert(alerts.get("email"), log_line)
        self._send_http_alert(alerts.get("http"), log_line)
        self._send_syslog_alert(alerts.get("syslog"), log_line)

    def _send_email_alert(self, cfg, log_line: str) -> None:
        if not cfg or not cfg.get("enabled"):
            return
        try:
            host = cfg.get("smtp_host")
            port = int(cfg.get("smtp_port", 587))
            username = cfg.get("username")
            password = cfg.get("password")
            sender = cfg.get("from")
            recipients = cfg.get("to")
            if isinstance(recipients, str):
                recipients = [recipients]
            subject = cfg.get("subject", "TaskMaster Alert")
            use_tls = cfg.get("use_tls", True)

            if not host or not sender or not recipients:
                return

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            msg.set_content(log_line)

            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if use_tls:
                    smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        except Exception:
            self._log_error("Email alert failed")

    def _send_http_alert(self, cfg, log_line: str) -> None:
        if not cfg or not cfg.get("enabled"):
            return
        try:
            url = cfg.get("url")
            if not url:
                return
            method = cfg.get("method", "POST").upper()
            headers = cfg.get("headers", {}) or {}
            timeout = float(cfg.get("timeout", 5))

            payload = {"message": log_line}
            data = json.dumps(payload).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout):
                pass
        except Exception:
            self._log_error("HTTP alert failed")

    def _send_syslog_alert(self, cfg, log_line: str) -> None:
        if not cfg or not cfg.get("enabled"):
            return
        try:
            address = cfg.get("address", "localhost")
            port = int(cfg.get("port", 514))
            facility = cfg.get("facility", "user")
            logger = logging.getLogger("taskmaster_syslog")
            if not any(isinstance(h, SysLogHandler) for h in logger.handlers):
                handler = SysLogHandler(address=(address, port), facility=facility)
                formatter = logging.Formatter("%(message)s")
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            logger.info(log_line)
        except Exception:
            self._log_error("Syslog alert failed")

    def _build_preexec_fn(self, item):
        user = item.get("user")
        group = item.get("group")
        if not user and not group:
            return None
        if os.name == "nt":
            return None
        if os.geteuid() != 0:
            raise PermissionError("Must be root to set user/group")

        uid = None
        gid = None

        if group:
            import grp
            gid = grp.getgrnam(group).gr_gid
        if user:
            import pwd
            pw = pwd.getpwnam(user)
            uid = pw.pw_uid
            if gid is None:
                gid = pw.pw_gid

        def _preexec():
            if gid is not None:
                os.setgid(gid)
            if uid is not None:
                os.setuid(uid)

        return _preexec

    def Monitor(self):
        while True:
            for prog in list(self.programs.keys()):
                item = self.programs[prog]
                procs = list(item.get("procs", []))

                for proc_info in list(procs):
                    proc = proc_info.get("proc")
                    if proc is None:
                        continue
                    ret = proc.poll()
                    if ret is None:
                        continue

                    run_time = time.time() - proc_info.get("start_time", time.time())
                    expected = ret in item.get("exitcodes", [0])
                    autorestart = item.get("autorestart")

                    should_restart = False
                    if autorestart is True:
                        should_restart = True
                    elif isinstance(autorestart, str) and autorestart.lower() == "unexpected":
                        should_restart = not expected

                    if run_time < item.get("starttime", 0):
                        proc_info["retries"] += 1
                        if proc_info["retries"] <= item.get("startretries", 0):
                            should_restart = True
                        else:
                            should_restart = False
                            self.log_info("Failed", prog, proc.pid, instance=proc_info.get("index"))
                    elif should_restart and item.get("startretries", 0) > 0:
                        proc_info["retries"] += 1
                        if proc_info["retries"] > item.get("startretries", 0):
                            should_restart = False
                            self.log_info("Failed", prog, proc.pid, instance=proc_info.get("index"))

                    self._close_output_handles(proc_info)

                    if should_restart:
                        self.log_info("Restarting", prog, proc.pid, instance=proc_info.get("index"))
                        new_proc_info = self._start_process(prog, item, proc_info.get("index", 1))
                        new_proc_info["retries"] = proc_info.get("retries", 0)
                        procs[procs.index(proc_info)] = new_proc_info
                        self.log_info("Started", prog, new_proc_info["proc"].pid, instance=new_proc_info.get("index"))
                    else:
                        self.log_info("Stopped", prog, proc.pid, instance=proc_info.get("index"))
                        procs.remove(proc_info)

                item["procs"] = procs
                self._update_program_status(item)
                if item.get("status") != "STARTED":
                    master_fd = item.get("pty_master")
                    if isinstance(master_fd, int):
                        try:
                            os.close(master_fd)
                        except OSError:
                            pass
                        item.pop("pty_master", None)

            time.sleep(5)
