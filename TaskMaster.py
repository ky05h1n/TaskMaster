import subprocess
import yaml
import time
import readline
import threading
from datetime import datetime


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"



class ControlShell:
    
        def __init__(self, Taskmaster):
            self.Taskmaster = Taskmaster

        def command_loop(self):
            print("\n" + "="*50)
            print("Taskmaster Control Shell")
            print("="*50)
            print("Type 'help' for commands\n")
            
            while True:
                try:
                    cmd = input("taskmaster> ").strip()
                    
                    if cmd == "":
                        continue
                except KeyboardInterrupt:
                    print(f"\n{YELLOW}Use 'quit' to exit{RESET}")


class TaskMaster:
    
        def __init__(self, configfile):
            self.configfile = configfile
            self.programs = {}
            self.pid_list = {}
            self.logfie = {}
            
        def log_info(self, message, prog=None, pid=None):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Symbols only (no colors for clean log file)
            if message == "Started":
                symbol = "▶"
            elif message == "Running":
                symbol = "●"
            elif message == "Terminated":
                symbol = "✖"
            elif message == "Restarting":
                symbol = "↻"
            else:
                symbol = "▪"
            
            if prog and pid:
                log_line = f"{symbol} [{timestamp}] [{prog}] [PID:{pid}] {message}"
            elif prog:
                log_line = f"{symbol} [{timestamp}] [{prog}] {message}"
            else:
                log_line = f"{symbol} [{timestamp}] {message}"
            with open("logs.log", "a") as log_file:
                log_file.write(f"{log_line}\n")
                

        def Run(self, programs=None):
            if programs is None:
                programs = self.programs
            for prog , item in programs.items():
                cmd = item.get('cmd')
                proc = subprocess.Popen(cmd.split())
                self.pid_list[proc.pid] = (proc, prog, item)
                self.log_info("Started", prog, proc.pid)
                time.sleep(1)
            return self.pid_list
        
        def Load_config(self):
            with open(self.configfile, 'r') as file:
                self.programs = yaml.safe_load(file)
            return self.programs['programs']
        
        def Monitor(self):
            while True:
                for pid in list(self.pid_list.keys()):
                    proc, prog, item = self.pid_list[pid]
                    autorestart = item.get('autorestart')
                    if proc.poll() is None:
                        self.log_info("Running", prog, proc.pid)
                        time.sleep(1)
                    else:
                        self.log_info("Terminated", prog, proc.pid)
                        self.pid_list.pop(pid)
                        time.sleep(1)
                        if autorestart == True:
                            self.log_info("Restarting", prog)
                            time.sleep(1)
                            self.pid_list.update(self.Run({prog: item}))
                    
                
if __name__ == "__main__":
    
    
    Obj = TaskMaster("conf.yaml")
    Obj.programs = Obj.Load_config()
    Obj.pid_list.update(Obj.Run())
    
    Thread_Monitor = threading.Thread(target=Obj.Monitor)
    Thread_Monitor.daemon = True
    Thread_Monitor.start()
    
    Ctl = ControlShell(Obj)
    Ctl.command_loop()
    