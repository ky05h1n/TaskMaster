import subprocess
import yaml
import time 


def read_conf():
    
    with open("conf.yaml", 'r') as file :
        config = yaml.safe_load(file)
    return config['programs']


def run_progrms(obj):
    
    pid_list = {}
    for prog , item in obj.items():
        cmd = item.get('cmd')
        proc = subprocess.Popen(cmd.split())
        pid_list[proc.pid] = (proc, prog, item)
        print(f"Started program: {prog} with PID: {proc.pid}")
    return pid_list


def check_auto0start(item):
    autostart = item.get('autostart', False)
    return autostart

def chek_status(pid_list, obj):
    
    while pid_list:
        for pid in list(pid_list.keys()):
            proc, prog, item = pid_list[pid]
            autorestart = item.get('autorestart')
            if proc.poll() is None:
                print(f"Program {prog} with PID: {proc.pid} is still running.")
            else:
                print(f"Program {prog} with PID: {proc.pid} has terminated.")
                pid_list.pop(pid)
            if autorestart == True:
                print(f"Restarting program: {prog}")            
                
        time.sleep(1)

if __name__ == "__main__":
    
    
    obj = read_conf()
    pid_list = run_progrms(obj)
    chek_status(pid_list, obj)
    
    