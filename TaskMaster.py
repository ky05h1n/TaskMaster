import subprocess
import yaml
import time
# import readline
import threading
import os
import json
import logging
from logging.handlers import SysLogHandler
import smtplib
from email.message import EmailMessage
import urllib.request
from datetime import datetime

LOGFILE = "logs.log"
CONFILE = "conf.yaml"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"



class ControlShell:
    
        def __init__(self, Taskmaster):
            self.Taskmaster = Taskmaster
            
        def cmd_help(self):
            print("\nAvailable commands:")
            print("  help               - Show this help")
            print("  status             - Show program status")
            print("  quit               - Exit taskmaster")
            print("  start [program]    - Start a program")
            print("  stop [program]     - Stop a program")
            print("  restart [program]  - Restart a program")
            print("  reload             - Reload configuration file")
            print()

        def cmd_status(self):
            
            
            
            print()
            print(f"{'─'*60}")
            print(f"  {'PROGRAM':<15} {'PID':<10} {'STATUS':<12} {'CMD'}")
            print(f"{'─'*60}")
            
            for prog in list(self.Taskmaster.programs.keys()):
                proc, items = self.Taskmaster.programs[prog]
                status = items.get("status")

                cmd = items.get("cmd", "N/A")
                if status == "CREATED":
                    status_icon = f"{RED}▪ STOPPED{RESET}"
                    print(f"  {prog:<15} {'-':<10} {status_icon:<21} {cmd}")
                else:
                    if status == "STARTED":
                        status_icon = f"{GREEN}● RUNNING{RESET}"
                        print(f"  {prog:<15} {proc.pid:<10} {status_icon:<21} {cmd}")

                    elif status == "STOPPED":
                        status_icon = f"{RED}▪ STOPPED{RESET}"
                        print(f"  {prog:<15} {proc.pid:<10} {status_icon:<21} {cmd}")
            
            print(f"{'─'*60}")
            print(f"  Total: {len(self.Taskmaster.programs)} program(s)")
            print()
                
        def cmd_start(self, target):
            
            proc, items = self.Taskmaster.programs[target]
            items["sig"] = "START"
            self.Taskmaster.Run({target: items})
            print(f"{GREEN}Program '{target}' started successfully.{RESET}")
            items["sig"] = None
            
        def cmd_stop(self, target):
            proc, items = self.Taskmaster.programs[target]
            proc.terminate()
            items["status"] = "STOPPED"
            self.Taskmaster.log_info("Stopped", target, proc.pid)
            print(f"{RED}Program '{target}' stopped successfully.{RESET}")
            
        def cmd_restart(self, target):
            
            self.cmd_stop(target)
            time.sleep(1)
            self.cmd_start(target)
            print(f"{GREEN}Program '{target}' restarted successfully.{RESET}")
            self.Taskmaster.log_info("Restarted", target)
        
        def cmd_reload_config(self):
            sig = False
            new_conf = self.Taskmaster.Load_config("reload")
            for prog_new , items_new in new_conf.items():
                if prog_new not in self.Taskmaster.programs:
                    items_new['status'] = "CREATED"
                    items_new['sig'] = None
                    self.Taskmaster.programs[prog_new] = (None, items_new)
                    print(f"{GREEN}Configuration reloaded successfully.{RESET}")
                    sig = True
                elif prog_new in self.Taskmaster.programs:
                    proc , items = self.Taskmaster.programs[prog_new]
                    save = items.pop('status', (None))
                    items.pop('sig', (None))
                    items_new.pop('status', (None))
                    items_new.pop('sig', (None))
                    if items_new != items:
                        items_new['status'] = "CREATED"
                        items_new['sig'] = None
                        if proc is not None:
                            proc.terminate()
                        proc = None
                        self.Taskmaster.programs[prog_new] = (proc, items_new)
                        print(f"{GREEN}Configuration reloaded successfully.{RESET}")
                        self.Taskmaster.Run({prog_new: items_new})
                        sig = True
                    else:
                        items['status'] = save
                        items['sig'] = None
                        self.Taskmaster.programs[prog_new] = (proc, items)
            for prog in list(self.Taskmaster.programs.keys()):
                if prog not in new_conf:
                    proc , items = self.Taskmaster.programs[prog]
                    if proc is not None:
                        proc.terminate()
                    self.Taskmaster.programs.pop(prog)
                    print(f"{GREEN}Configuration reloaded successfully.{RESET}")
                    sig = True
            if not sig:
                print(f"{GREEN}Configuration reloaded, Nothing Changed!{RESET}")
            self.Taskmaster.log_info("Configuration Reloaded")
            
        
        def check_program(self, cmd, target):
      
            
            if cmd == "start" or cmd == "stop" or cmd == "restart":
                if target is None:
                    print(f"{RED}Error: No program specified for '{cmd}' command.{RESET}")
                    return True            
                if target not in self.Taskmaster.programs:
                    print(f"{RED}Error: Program '{target}' not found.{RESET}")
                    return True
                if  cmd == "start":
                    proc, items = self.Taskmaster.programs[target]
                    if items.get("status") == "STARTED":
                        print(f"{GREEN}Program '{target}' is already running.{RESET}")
                        return True
                if cmd == "stop" or cmd == "restart":
                    proc, items = self.Taskmaster.programs[target]
                    if items.get('status') != "STARTED":
                        print(f"{RED}Program '{target}' is not running.{RESET}")
                        return True
                return None

        def command_input(self):
            print("\n" + "="*50)
            print("Taskmaster Control Shell")
            print("="*50)
            print("Type 'help' for commands\n")
            
            while True:
                try:
                    inpt = input("taskmaster> ").strip()
                    
                    if inpt == "":
                        continue
                    comands = inpt.split(maxsplit=1)
                    cmd = comands[0] 
                    target = comands[1] if len(comands) > 1 else None
                    if self.check_program(cmd, target):
                        continue
                    if cmd == "quit" or cmd == "exit":
                        print(f"{YELLOW}Shutting down taskmaster...{RESET}")
                        break

                    elif cmd == "help" and target is None:
                        self.cmd_help()
                
                    elif cmd == "status" and target is None:
                        self.cmd_status()
                    

                    elif cmd == "reload" and target is None:
                        self.cmd_reload_config()

                    elif cmd == "start":
                        self.cmd_start(target)
                        
                    elif cmd == "stop":
                        self.cmd_stop(target)
                        
                    elif cmd == "restart":
                        self.cmd_restart(target)
                
                    else:
                        print(f"{RED}Unknown command: '{cmd}'{RESET}")
                
                except KeyboardInterrupt:
                    print(f"\n{YELLOW}Use 'quit' to exit{RESET}")
                except EOFError:
                    print(f"\n{YELLOW}Use 'quit' to exit{RESET}")


class TaskMaster:
    
        def __init__(self, configfile):
            self.configfile = configfile
            self.configdata = {}
            self.programs = {}
            self.logfie = {}
            self.alerts = {}
            
        def log_info(self, message, prog=None, pid=None):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            
            if message == "Started":
                symbol = "▶"
            elif message == "Stopped":
                symbol = "▪"
            elif message == "Restarting" or message == "Restarted":
                symbol = "↻"
            if prog and pid:
                log_line = f"{symbol} [{timestamp}] [{prog}] [PID:{pid}] {message}"
            elif prog:
                log_line = f"{symbol} [{timestamp}] [{prog}] {message}"
            else:
                symbol = "↻"
                log_line = f"{symbol} [{timestamp}] {message}"
            with open(LOGFILE, "a", encoding="utf-8") as log_file:
                log_file.write(f"{log_line}\n")
                time.sleep(0.5)       
            self._send_alerts(log_line)

        def Run(self, programs=None):
            if programs is None:
                programs = self.configdata
                print()
                print(f"{CYAN}{'═'*60}{RESET}")
                print(f"{CYAN}  ▶ TASKMASTER - Starting Programs{RESET}")
                print(f"{CYAN}{'═'*60}{RESET}")
                print()
                time.sleep(0.5)
                print(f"  {'PROGRAM':<15} {'STATUS':<20} {'PID'}")
                print(f"  {'─'*50}")
                time.sleep(0.3)
            
            for prog, item in programs.items():
                cmd = item.get('cmd')
                if programs == self.configdata:
                    item["status"] = "CREATED"
                    print(f"  {prog:<15} {YELLOW}◌ Loading...{RESET}", end='\r')
                    time.sleep(0.4)
                    
                if item.get('autostart') or item.get('sig') == "START":
                    preexec_fn = self._build_preexec_fn(item)
                    proc = subprocess.Popen(
                        cmd.split(),
                        stdout=subprocess.DEVNULL,
                        preexec_fn=preexec_fn
                    )
                    item["status"] = "STARTED"
                    self.programs[prog] = (proc, item)
                    self.log_info("Started", prog, proc.pid)
                    if programs == self.configdata:
                        print(f"  {prog:<15} {GREEN}● Started{RESET}            {proc.pid}")
                        time.sleep(0.3)
                if item.get('status') == "CREATED":
                    proc = None
                    self.programs[prog] = (proc, item)
    
            if programs == self.configdata:
                time.sleep(0.3)
                print(f"  {'─'*50}")
                time.sleep(0.2)
                if prog is None:
                    print(f"  {GREEN}✓ {len(self.programs)} program(s) started successfully{RESET}")
                    print()
                else:
                    print(f"  {GREEN}✓ {len(self.programs)} program(s) loaded {RESET}")
                    print()
                
            
            return self.programs
        
        def Load_config(self, state=None):
            
                with open(self.configfile, 'r') as file:
                    data = yaml.safe_load(file)
                if state == "reload":
                    return data['programs']
                else:
                    self.configdata = data['programs']
                    self.alerts = data.get('alerts', {}) or {}
                
      
        def Monitor(self):

            while True:
                for prog in list(self.programs.keys()):
                    proc, item = self.programs[prog]
                    
                    if item.get("status") == "CREATED" or item.get("status") == "STOPPED":
                        continue
                    if proc.poll() is None:
                        continue
                    else:
                        self.log_info("Stopped", prog, proc.pid)
                        item ["status"] = "STOPPED"
                        if item.get("autorestart"):
                            self.log_info("Restarting", prog)
                            self.Run({prog: item})
                time.sleep(5)

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
                return

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
                return

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
                return

        def _build_preexec_fn(self, item):
            user = item.get("user")
            group = item.get("group")
            if not user and not group:
                return None
            if os.name == "nt":
                return None

            def _preexec():
                if group:
                    import grp
                    gid = grp.getgrnam(group).gr_gid
                    os.setgid(gid)
                if user:
                    import pwd
                    uid = pwd.getpwnam(user).pw_uid
                    os.setuid(uid)

            return _preexec
                
if __name__ == "__main__":
    
    with open(LOGFILE, "w", encoding="utf-8") as logfile:
                logfile.write("")
    Obj = TaskMaster(CONFILE)
    Obj.Load_config()
    Obj.Run()
    
    Thread_Monitor = threading.Thread(target=Obj.Monitor)
    Thread_Monitor.daemon = True
    Thread_Monitor.start()
    
    Ctl = ControlShell(Obj)
    Ctl.command_input()
    