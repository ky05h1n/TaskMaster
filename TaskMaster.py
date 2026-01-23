import subprocess
import yaml
import time
import readline
import threading
from datetime import datetime

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
            
            
            for prog in list(self.Taskmaster.programs.keys()):
                proc, items = self.Taskmaster.programs[prog]
                status = items.get("status")
                if status == "RUNNING":
                    status_msg = f"{GREEN}RUNNING{RESET}"
                elif status == "STOPED":
                    status_msg = f"{RED}STOPED{RESET}"
                print(f"Program: {prog} | PID: {proc.pid} | Status: {status_msg}")
                
        def cmd_start(self):
            pass
        def cmd_stop(self):
            pass
        def cmd_restart(self):
            pass
        def cmd_reload_config(self):
            pass
        
        def check_program(self):
            pass
            
        def command_loop(self):
            print("\n" + "="*50)
            print("Taskmaster Control Shell")
            print("="*50)
            print("Type 'help' for commands\n")
            
            while True:
                try:
                    input = input("taskmaster> ").strip()
                    comands = input.split()
                    cmd = comands[0] if len(comands) > 1 else None
                    
                    if cmd == "":
                        continue
                    elif cmd == "quit" or cmd == "exit":
                        print(f"{YELLOW}Shutting down taskmaster...{RESET}")
                        break

                    elif cmd == "help":
                        self.cmd_help()
                
                    elif cmd == "status":
                        self.cmd_status()
                    
                    elif cmd == "start":
                        self.cmd_start()
                        
                    elif cmd == "stop":
                        self.cmd_stop()
                        
                    elif cmd == "restart":
                        self.cmd_restart()
                        
                    elif cmd == "reload_config":
                        self.cmd_reload_config()
                
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
            
        def log_info(self, message, prog=None, pid=None):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Symbols only (no colors for clean log file)
            if message == "Started":
                symbol = "▶"
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
                programs = self.configdata
            for prog , item in programs.items():
                cmd = item.get('cmd')
                proc = subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL)
                item["status"] = "RUNNING"
                self.programs[prog] = (proc, item)
                self.log_info("Started", prog, proc.pid)
            return self.programs
        
        def Load_config(self):
            with open(self.configfile, 'r') as file:
                data = yaml.safe_load(file)
            self.configdata = data['programs']
        
        def Monitor(self):
            while True:
                for prog in list(self.programs.keys()):
                    proc, item = self.programs[prog]
                    autorestart = item.get('autorestart')
                    if proc.poll() is None:
                        continue
                    else:
                        self.log_info("Terminated", prog, proc.pid)
                        item ["status"] = "STOPED"
                        if autorestart == True:
                            self.log_info("Restarting", prog)
                            self.Run({prog: item})
                time.sleep(1)
                
if __name__ == "__main__":
    
    
    Obj = TaskMaster(CONFILE)
    Obj.Load_config()
    Obj.Run()
    
    Thread_Monitor = threading.Thread(target=Obj.Monitor)
    Thread_Monitor.daemon = True
    Thread_Monitor.start()
    
    Ctl = ControlShell(Obj)
    Ctl.command_loop()
    