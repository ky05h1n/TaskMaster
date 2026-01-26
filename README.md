# TaskMaster

A lightweight process manager for Linux, similar to Supervisord. TaskMaster allows you to manage, monitor, and control multiple processes from a simple command-line interface.

## Features

- **Process Management**: Start, stop, and restart programs
- **Auto-start**: Automatically start programs on launch
- **Auto-restart**: Automatically restart programs when they exit
- **Live Monitoring**: Background thread monitors process status
- **Configuration Reload**: Hot-reload configuration without restarting TaskMaster
- **Logging**: All events logged to `logs.log`
- **Interactive Shell**: User-friendly command interface with colored output

## Installation

```bash
git clone https://github.com/ky05h1n/TaskMaster.git
cd TaskMaster
pip install pyyaml
```

## Configuration

Edit `conf.yaml` to define your programs:

```yaml
programs:
  my_program:
    cmd: "/path/to/command arg1 arg2"
    autostart: true
    autorestart: true
  
  another_program:
    cmd: "python3 script.py"
    autostart: false
    autorestart: false
```

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `cmd` | string | Command to execute |
| `autostart` | boolean | Start program automatically on TaskMaster launch |
| `autorestart` | boolean | Restart program automatically when it exits |

## Usage

Start TaskMaster:

```bash
python3 TaskMaster.py
```

### Available Commands

| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `status` | Display status of all programs |
| `start <program>` | Start a specific program |
| `stop <program>` | Stop a specific program |
| `restart <program>` | Restart a specific program |
| `reload` | Reload configuration file |
| `quit` / `exit` | Exit TaskMaster |

### Example Session

```
════════════════════════════════════════════════════════════
  ▶ TASKMASTER - Starting Programs
════════════════════════════════════════════════════════════

  PROGRAM         STATUS               PID
  ──────────────────────────────────────────────────
  sleeper1        ● Started            12345
  sleeper2        ● Started            12346
  ──────────────────────────────────────────────────
  ✓ 2 program(s) loaded

==================================================
Taskmaster Control Shell
==================================================
Type 'help' for commands

taskmaster> status
────────────────────────────────────────────────────────────
  PROGRAM         PID        STATUS       CMD
────────────────────────────────────────────────────────────
  sleeper1        12345      ● RUNNING    sleep 10
  sleeper2        12346      ● RUNNING    sleep 5
────────────────────────────────────────────────────────────
  Total: 2 program(s)

taskmaster> stop sleeper1
Program 'sleeper1' stopped successfully.

taskmaster> reload
Configuration reloaded, Nothing Changed!

taskmaster> quit
Shutting down taskmaster...
```

## Log Format

Events are logged to `logs.log`:

```
▶ [2026-01-26 12:00:00] [sleeper1] [PID:12345] Started
▪ [2026-01-26 12:00:10] [sleeper1] [PID:12345] Stopped
↻ [2026-01-26 12:00:10] [sleeper1] Restarting
▶ [2026-01-26 12:00:11] [sleeper1] [PID:12350] Started
↻ [2026-01-26 12:00:15] Configuration Reloaded
```

## Project Structure

```
TaskMaster/
├── TaskMaster.py    # Main application
├── conf.yaml        # Configuration file
├── logs.log         # Log file
└── README.md        # This file
```

## License

MIT License
