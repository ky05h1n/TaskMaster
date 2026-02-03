import json
import socket
from typing import Optional, Dict, Any, List


HOST = "127.0.0.1"
PORT = 8765

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def _send_command(cmd: str, target: Optional[str] = None) -> Dict[str, Any]:
    payload = {"cmd": cmd, "target": target}
    with socket.create_connection((HOST, PORT)) as sock:
        reader = sock.makefile("r", encoding="utf-8")
        writer = sock.makefile("w", encoding="utf-8")
        writer.write(json.dumps(payload) + "\n")
        writer.flush()
        line = reader.readline()
        if not line:
            return {"ok": False, "message": "No response from server"}
        return json.loads(line)


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

            response = _send_command(cmd, target)
            if not response.get("ok"):
                print(f"{RED}{response.get('message', 'Command failed')}{RESET}")
                if cmd in ("quit", "exit"):
                    break
                continue

            if cmd == "status":
                _print_status(response.get("data", []))
            else:
                print(f"{GREEN}{response.get('message', 'OK')}{RESET}")

            if cmd in ("quit", "exit"):
                break

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Use 'quit' to exit{RESET}")
        except EOFError:
            print(f"\n{YELLOW}Use 'quit' to exit{RESET}")
        except ConnectionRefusedError:
            print(f"{RED}Cannot connect to server on {HOST}:{PORT}{RESET}")
        except Exception as exc:
            print(f"{RED}Client error: {exc}{RESET}")


if __name__ == "__main__":
    main()
