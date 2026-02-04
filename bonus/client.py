import json
import socket
import os
import sys
import select
import termios
import tty
from typing import Optional, Dict, Any, List


HOST = "127.0.0.1"
PORT = 8765
SOCKET_PATH = "/tmp/taskmaster.sock"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def _send_command(cmd: str, target: Optional[str] = None) -> Dict[str, Any]:
    payload = {"cmd": cmd, "target": target}
    if os.name == "nt":
        sock = socket.create_connection((HOST, PORT))
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
    with sock:
        reader = sock.makefile("r", encoding="utf-8")
        writer = sock.makefile("w", encoding="utf-8")
        writer.write(json.dumps(payload) + "\n")
        writer.flush()
        line = reader.readline()
        if not line:
            return {"ok": False, "message": "No response from server"}
        return json.loads(line)


def _open_socket() -> socket.socket:
    if os.name == "nt":
        return socket.create_connection((HOST, PORT))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    return sock


def _attach_console(target: str) -> None:
    sock = _open_socket()
    try:
        payload = {"cmd": "attach", "target": target}
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        line = b""
        while not line.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                print(f"{RED}No response from server{RESET}")
                return
            line += chunk
        response = json.loads(line.decode("utf-8"))
        if not response.get("ok"):
            print(f"{RED}{response.get('message', 'Command failed')}{RESET}")
            return

        print(f"{GREEN}{response.get('message', 'Attached')}{RESET}")

        stdin_fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(stdin_fd)
        try:
            tty.setraw(stdin_fd)
            sock.setblocking(False)
            while True:
                rlist, _, _ = select.select([stdin_fd, sock], [], [], 0.2)
                if not rlist:
                    try:
                        probe = sock.recv(1, socket.MSG_PEEK)
                        if probe == b"":
                            break
                    except BlockingIOError:
                        continue
                    except OSError:
                        break
                if stdin_fd in rlist:
                    data = os.read(stdin_fd, 1024)
                    if not data:
                        break
                    if b"\x1d" in data:
                        sock.sendall(b"\x1d")
                        break
                    sock.sendall(data)
                if sock in rlist:
                    try:
                        data = sock.recv(1024)
                    except BlockingIOError:
                        continue
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
        finally:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            print(f"\n{YELLOW}Detached.{RESET}")
    finally:
        sock.close()


def _print_help() -> None:
    print("\nAvailable commands:")
    print("  help               - Show this help")
    print("  status             - Show program status")
    print("  quit               - Exit taskmaster")
    print("  start [program]    - Start a program")
    print("  stop [program]     - Stop a program")
    print("  restart [program]  - Restart a program")
    print("  reload             - Reload configuration file")
    print()


def _print_status(programs: List[Dict[str, Any]]) -> None:
    print()
    print(f"{'─'*60}")
    print(f"  {'PROGRAM':<15} {'PID':<10} {'STATUS':<12} {'CMD'}")
    print(f"{'─'*60}")

    for entry in programs:
        name = entry.get("name")
        pid = entry.get("pid") or "-"
        status = entry.get("status")
        cmd = entry.get("cmd", "N/A")

        if status == "STARTED":
            status_icon = f"{GREEN}● RUNNING{RESET}"
        else:
            status_icon = f"{RED}▪ STOPPED{RESET}"
        print(f"  {name:<15} {pid!s:<10} {status_icon:<21} {cmd}")

    print(f"{'─'*60}")
    print(f"  Total: {len(programs)} program(s)")
    print()


def _validate_program(cmd: str, target: Optional[str]) -> bool:
    if cmd in ("start", "stop", "restart") and not target:
        print(f"{RED}Error: No program specified for '{cmd}' command.{RESET}")
        return False
    return True


def main() -> None:
    print("\n" + "=" * 50)
    print("Taskmaster Control Shell (Client)")
    print("=" * 50)
    print("Type 'help' for commands\n")

    while True:
        try:
            inpt = input("taskmaster> ").strip()
            if inpt == "":
                continue

            parts = inpt.split(maxsplit=1)
            cmd = parts[0]
            target = parts[1] if len(parts) > 1 else None

            if cmd in ("help", "?"):
                _print_help()
                continue

            if not _validate_program(cmd, target):
                continue

            if cmd == "attach":
                if not target:
                    print(f"{RED}Error: No program specified for 'attach' command.{RESET}")
                    continue
                try:
                    _attach_console(target)
                except FileNotFoundError:
                    print(f"{RED}Cannot connect to server (socket not found){RESET}")
                except ConnectionRefusedError:
                    print(f"{RED}Cannot connect to server on {HOST}:{PORT}{RESET}")
                continue

            if cmd in ("quit", "exit"):
                try:
                    response = _send_command(cmd, target)
                    if response.get("ok"):
                        print(f"{GREEN}{response.get('message', 'OK')}{RESET}")
                    else:
                        print(f"{RED}{response.get('message', 'Command failed')}{RESET}")
                except ConnectionRefusedError:
                    print(f"{YELLOW}Server not running; exiting client.{RESET}")
                except FileNotFoundError:
                    print(f"{YELLOW}Server socket not found; exiting client.{RESET}")
                break

            try:
                response = _send_command(cmd, target)
            except ConnectionRefusedError:
                print(f"{RED}Cannot connect to server on {HOST}:{PORT}{RESET}")
                continue
            except FileNotFoundError:
                print(f"{RED}Cannot connect to server (socket not found){RESET}")
                continue

            if not response.get("ok"):
                message = response.get("message", "Command failed")
                print(f"{RED}{message}{RESET}")
                continue

            if cmd == "status":
                _print_status(response.get("data", []))
            else:
                print(f"{GREEN}{response.get('message', 'OK')}{RESET}")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Use 'quit' to exit{RESET}")
        except EOFError:
            print(f"\n{YELLOW}Use 'quit' to exit{RESET}")
        except ConnectionRefusedError:
            print(f"{RED}Cannot connect to server on {HOST}:{PORT}{RESET}")
        except FileNotFoundError:
            print(f"{RED}Cannot connect to server (socket not found){RESET}")
        except Exception as exc:
            print(f"{RED}Client error: {exc}{RESET}")


if __name__ == "__main__":
    main()
