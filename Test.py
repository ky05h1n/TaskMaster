import subprocess
import yaml
import time
import readline
import threading


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


class TaskMaster:
    
    def __init__(self, configfile):
        self.configfile = configfile
        self.programs = {}
        self.pid_list = {}

    def run(self, programs=None):
        if programs is None:
            programs = self.programs
        for prog , item in programs.items():
            cmd = item.get('cmd')
            proc = subprocess.Popen(cmd.split())
            self.pid_list[proc.pid] = (proc, prog, item)
            print(f"{CYAN}▶ Started program: {prog} with PID: {proc.pid}{RESET}")
            time.sleep(1)
        return self.pid_list
    
    def load_config(self):
        with open(self.configfile, 'r') as file:
            self.programs = yaml.safe_load(file)
        return self.programs['programs']
    
    def monitor(self):
        
            for pid in list(self.pid_list.keys()):
                proc, prog, item = self.pid_list[pid]
                autorestart = item.get('autorestart')
                if proc.poll() is None:
                    print(f"{GREEN}● Program {prog} with PID: {proc.pid} is still running.{RESET}")
                    time.sleep(1)
                else:
                    print(f"{RED}✖ Program {prog} with PID: {proc.pid} has terminated.{RESET}")
                    self.pid_list.pop(pid)
                    time.sleep(1)
                    if autorestart == True:
                        print(f"{YELLOW}↻ Restarting program: {prog}{RESET}")
                        time.sleep(1)
                        self.pid_list.update(self.run({prog: item}))
                
                
if __name__ == "__main__":
    
    
    Obj = TaskMaster("conf.yaml")
    Obj.programs = Obj.load_config()
    Obj.pid_list.update(Obj.run())
    while True:
        Obj.monitor()