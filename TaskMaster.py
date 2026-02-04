import subprocess
import yaml
import time
import readline
import threading
import os
import signal
import shlex
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
                items = self.Taskmaster.programs[prog]
                status = items.get("status")

                cmd = items.get("cmd", "N/A")
                procs = items.get("procs", [])
                running_procs = [p for p in procs if p.get("proc") and p["proc"].poll() is None]
                pid_list = ",".join(str(p["proc"].pid) for p in running_procs) if running_procs else "-"
                total_expected = items.get("numprocs", 1)

                if status == "CREATED":
                    status_icon = f"{RED}▪ STOPPED{RESET}"
                    print(f"  {prog:<15} {pid_list:<10} {status_icon:<21} {cmd}")
                else:
                    if status == "STARTED":
                        status_icon = f"{GREEN}● RUNNING{RESET}"
                        print(f"  {prog:<15} {pid_list:<10} {status_icon:<21} {cmd} ({len(running_procs)}/{total_expected})")

                    elif status == "STOPPED":
                        status_icon = f"{RED}▪ STOPPED{RESET}"
                        print(f"  {prog:<15} {pid_list:<10} {status_icon:<21} {cmd}")
            
            print(f"{'─'*60}")
            print(f"  Total: {len(self.Taskmaster.programs)} program(s)")
            print()
                
        def cmd_start(self, target):
            self.Taskmaster.start_program(target)
            print(f"{GREEN}Program '{target}' started successfully.{RESET}")
            
        def cmd_stop(self, target):
            self.Taskmaster.stop_program(target)
            print(f"{RED}Program '{target}' stopped successfully.{RESET}")
            
        def cmd_restart(self, target):
            self.Taskmaster.restart_program(target)
            print(f"{GREEN}Program '{target}' restarted successfully.{RESET}")
        
        def cmd_reload_config(self):
            changed = self.Taskmaster.reload_config()
            if changed:
                print(f"{GREEN}Configuration reloaded successfully.{RESET}")
            else:
                print(f"{GREEN}Configuration reloaded, Nothing Changed!{RESET}")
            
        
        def check_program(self, cmd, target):
      
            
            if cmd == "start" or cmd == "stop" or cmd == "restart":
                if target is None:
                    print(f"{RED}Error: No program specified for '{cmd}' command.{RESET}")
                    return True            
                if target not in self.Taskmaster.programs:
                    print(f"{RED}Error: Program '{target}' not found.{RESET}")
                    return True
                if  cmd == "start":
                    items = self.Taskmaster.programs[target]
                    if items.get("status") == "STARTED":
                        print(f"{GREEN}Program '{target}' is already running.{RESET}")
                        return True
                if cmd == "stop" or cmd == "restart":
                    items = self.Taskmaster.programs[target]
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
                    if self.Taskmaster.reload_requested:
                        self.Taskmaster.reload_requested = False
                        self.cmd_reload_config()
                    if self.Taskmaster.shutdown_requested:
                        print(f"{YELLOW}Shutting down taskmaster...{RESET}")
                        self.Taskmaster.shutdown()
                        break
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
                        self.Taskmaster.shutdown()
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
            self.reload_requested = False
            self.shutdown_requested = False
            self.lock = threading.Lock()

            self.defaults = {
                "numprocs": 1,
                "autostart": False,
                "autorestart": False,
                "exitcodes": [0],
                "starttime": 0,
                "startretries": 0,
                "stopsignal": "TERM",
                "stoptime": 10,
                "stdout": None,
                "stderr": None,
                "env": {},
                "workingdir": None,
                "umask": None,
            }
            
        def log_info(self, message, prog=None, pid=None, instance=None):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            
            if message == "Started":
                symbol = "▶"
            elif message == "Stopped":
                symbol = "▪"
            elif message == "Restarting" or message == "Restarted":
                symbol = "↻"
            elif message == "Failed":
                symbol = "✖"
            if prog and pid:
                name = f"{prog}:{instance}" if instance is not None else prog
                log_line = f"{symbol} [{timestamp}] [{name}] [PID:{pid}] {message}"
            elif prog:
                name = f"{prog}:{instance}" if instance is not None else prog
                log_line = f"{symbol} [{timestamp}] [{name}] {message}"
            else:
                symbol = "↻"
                log_line = f"{symbol} [{timestamp}] {message}"
            with open(LOGFILE, "a") as log_file:
                log_file.write(f"{log_line}\n")
                time.sleep(0.5)       

        def _parse_exitcodes(self, value):
            if value is None:
                return list(self.defaults["exitcodes"])
            if isinstance(value, list):
                return value
            return [value]

        def _parse_umask(self, value):
            if value is None:
                return None
            try:
                return int(str(value), 8)
            except ValueError:
                return None

        def _resolve_signal(self, name):
            if name is None:
                return signal.SIGTERM
            try:
                return getattr(signal, f"SIG{name}")
            except AttributeError:
                return signal.SIGTERM

        def _normalize_program_config(self, prog, item):
            normalized = dict(self.defaults)
            normalized.update(item or {})
            normalized["exitcodes"] = self._parse_exitcodes(normalized.get("exitcodes"))
            normalized["numprocs"] = int(normalized.get("numprocs", 1))
            normalized["starttime"] = int(normalized.get("starttime", 0))
            normalized["startretries"] = int(normalized.get("startretries", 0))
            normalized["stoptime"] = int(normalized.get("stoptime", 10))
            normalized["umask"] = self._parse_umask(normalized.get("umask"))
            normalized["stopsignal"] = normalized.get("stopsignal", "TERM")
            normalized["procs"] = normalized.get("procs", [])
            normalized["status"] = normalized.get("status", "CREATED")
            normalized["cmd"] = normalized.get("cmd", "")
            return normalized

        def _build_env(self, item):
            env = os.environ.copy()
            extra = item.get("env") or {}
            env.update({str(k): str(v) for k, v in extra.items()})
            return env

        def _open_output(self, path):
            if not path:
                return subprocess.DEVNULL
            if str(path).lower() == "discard":
                return subprocess.DEVNULL
            return open(path, "a")

        def _start_process(self, prog, item, index):
            cmd = item.get("cmd", "")
            argv = shlex.split(cmd)
            env = self._build_env(item)
            cwd = item.get("workingdir")
            umask_value = item.get("umask")

            stdout_handle = self._open_output(item.get("stdout"))
            stderr_handle = self._open_output(item.get("stderr"))

            def _apply_umask():
                if umask_value is not None:
                    os.umask(umask_value)

            proc = subprocess.Popen(
                argv,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
                cwd=cwd,
                preexec_fn=_apply_umask if umask_value is not None else None,
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

        def _close_output_handles(self, proc_info):
            for key in ("stdout_handle", "stderr_handle"):
                handle = proc_info.get(key)
                if handle not in (None, subprocess.DEVNULL):
                    try:
                        handle.close()
                    except Exception:
                        pass

        def _update_program_status(self, item):
            procs = item.get("procs", [])
            running = [p for p in procs if p.get("proc") and p["proc"].poll() is None]
            if running:
                item["status"] = "STARTED"
            elif procs:
                item["status"] = "STOPPED"
            else:
                item["status"] = "CREATED"

        def _config_signature(self, item):
            keys = [
                "cmd",
                "numprocs",
                "autostart",
                "autorestart",
                "exitcodes",
                "starttime",
                "startretries",
                "stopsignal",
                "stoptime",
                "stdout",
                "stderr",
                "env",
                "workingdir",
                "umask",
            ]
            return {k: item.get(k) for k in keys}

        def start_program(self, prog):
            item = self.programs.get(prog)
            if not item:
                return
            with self.lock:
                procs = item.get("procs", [])
                target = item.get("numprocs", 1)
                while len(procs) < target:
                    index = len(procs) + 1
                    try:
                        proc_info = self._start_process(prog, item, index)
                        procs.append(proc_info)
                        self.log_info("Started", prog, proc_info["proc"].pid, instance=index)
                    except Exception:
                        self.log_info("Failed", prog, instance=index)
                        break
                item["procs"] = procs
                self._update_program_status(item)

        def stop_program(self, prog):
            item = self.programs.get(prog)
            if not item:
                return
            stopsignal = self._resolve_signal(item.get("stopsignal"))
            stoptime = item.get("stoptime", 10)
            with self.lock:
                for proc_info in list(item.get("procs", [])):
                    proc = proc_info.get("proc")
                    if proc is None:
                        continue
                    try:
                        proc.send_signal(stopsignal)
                        proc.wait(timeout=stoptime)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    except Exception:
                        pass
                    self.log_info("Stopped", prog, proc.pid, instance=proc_info.get("index"))
                    self._close_output_handles(proc_info)
                item["procs"] = []
                self._update_program_status(item)

        def restart_program(self, prog):
            self.stop_program(prog)
            time.sleep(1)
            self.start_program(prog)
            self.log_info("Restarted", prog)

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
                if programs == self.configdata:
                    runtime_item = self.programs.get(prog, item)
                    runtime_item["status"] = "CREATED"
                    print(f"  {prog:<15} {YELLOW}◌ Loading...{RESET}", end='\r')
                    time.sleep(0.4)

                if item.get("autostart"):
                    self.start_program(prog)

                if programs == self.configdata:
                    runtime_item = self.programs.get(prog, item)
                    status = runtime_item.get("status")
                    procs = runtime_item.get("procs", [])
                    running = [p for p in procs if p.get("proc") and p["proc"].poll() is None]
                    pid_list = ",".join(str(p["proc"].pid) for p in running) if running else "-"
                    if status == "STARTED":
                        print(f"  {prog:<15} {GREEN}● Started{RESET}            {pid_list}")
                    else:
                        print(f"  {prog:<15} {YELLOW}◌ Loaded{RESET}             {pid_list}")
                        time.sleep(0.3)

            if programs == self.configdata:
                time.sleep(0.3)
                print(f"  {'─'*50}")
                time.sleep(0.2)
                print(f"  {GREEN}✓ {len(self.programs)} program(s) loaded {RESET}")
                print()

            return self.programs
        
        def Load_config(self, state=None):
                with open(self.configfile, 'r') as file:
                    data = yaml.safe_load(file)
                programs = data.get('programs', {})
                normalized = {}
                for prog, item in programs.items():
                    normalized[prog] = self._normalize_program_config(prog, item)
                if state == "reload":
                    return normalized
                else:
                    self.configdata = normalized
                    self.programs = {prog: dict(item) for prog, item in normalized.items()}

        def reload_config(self):
            changed = False
            new_conf = self.Load_config("reload")

            for prog_new, items_new in new_conf.items():
                if prog_new not in self.programs:
                    items_new["status"] = "CREATED"
                    items_new["procs"] = []
                    self.programs[prog_new] = items_new
                    if items_new.get("autostart"):
                        self.start_program(prog_new)
                    changed = True
                else:
                    current = self.programs[prog_new]
                    if self._config_signature(items_new) != self._config_signature(current):
                        self.stop_program(prog_new)
                        items_new["status"] = "CREATED"
                        items_new["procs"] = []
                        self.programs[prog_new] = items_new
                        if items_new.get("autostart"):
                            self.start_program(prog_new)
                        changed = True
                    else:
                        self.programs[prog_new].update(items_new)

           
            for prog in list(self.programs.keys()):
                if prog not in new_conf:
                    self.stop_program(prog)
                    self.programs.pop(prog)
                    changed = True

            self.log_info("Configuration Reloaded")
            return changed

        def request_reload(self, signum, frame):
            self.reload_requested = True

        def request_shutdown(self, signum, frame):
            self.shutdown_requested = True

        def shutdown(self):
            self.shutdown_requested = True
            for prog in list(self.programs.keys()):
                self.stop_program(prog)
            self.log_info("Stopped")
                
      
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

                time.sleep(5)
                
if __name__ == "__main__":
    
    with open(LOGFILE, 'w') as logfile:
                logfile.write("")
    Obj = TaskMaster(CONFILE)
    Obj.Load_config()

    signal.signal(signal.SIGHUP, Obj.request_reload)
    signal.signal(signal.SIGTERM, Obj.request_shutdown)
    signal.signal(signal.SIGINT, Obj.request_shutdown)

    Obj.Run()
    
    Thread_Monitor = threading.Thread(target=Obj.Monitor)
    Thread_Monitor.daemon = True
    Thread_Monitor.start()
    
    Ctl = ControlShell(Obj)
    Ctl.command_input()
    