# TaskMaster

A lightweight process manager for Linux, similar to Supervisord. TaskMaster allows you to manage, monitor, and control multiple processes from a simple command-line interface.

> ⚠️ **Work in Progress** - This project is under active development.

## Project Status

### ✅ Implemented

- [x] Start jobs as child processes
- [x] Monitor process status (alive/dead)
- [x] YAML configuration file
- [x] Logging system to local file
- [x] Interactive control shell with readline (line editing, history)
- [x] `status` command - view all programs
- [x] `start <program>` command
- [x] `stop <program>` command
- [x] `restart <program>` command (with 1s delay between stop/start)
- [x] `reload` command - hot reload configuration
- [x] `quit/exit` command
- [x] `autostart` - start program on launch
- [x] `autorestart` - restart on exit (`true` or `unexpected`)
- [x] Detect new/changed/removed programs on reload
- [x] Handle removed programs on reload (stop & remove)

### 🔄 In Progress

### ❌ TODO

**Bonus Ideas:**
- [ ] Client/server architecture (daemon + control program)
- [ ] Email/HTTP alerts
- [ ] Attach/detach to process console (like tmux)

### ✅ Implemented (Configuration Options)

- [x] `numprocs` - number of processes to start and keep running
- [x] `autorestart: unexpected` - restart only on unexpected exits
- [x] `exitcodes` - expected exit status codes
- [x] `starttime` - time before considered "successfully started"
- [x] `startretries` - max restart attempts before aborting
- [x] `stopsignal` - signal to use for graceful stop (TERM, HUP, INT, etc.)
- [x] `stoptime` - grace period before SIGKILL
- [x] `stdout/stderr` - redirect to files
- [x] `env` - environment variables
- [x] `workingdir` - working directory
- [x] `umask` - file creation mask

### ✅ Implemented (Signals)

- [x] SIGHUP reloads configuration
- [x] SIGTERM/SIGINT trigger graceful shutdown

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
  web:
    cmd: "python3 -m http.server 8080"
    numprocs: 1
    autostart: true
    autorestart: unexpected
    exitcodes: [0, 2]
    starttime: 2
    startretries: 3
    stopsignal: TERM
    stoptime: 10
    stdout: "/tmp/taskmaster.web.out"
    stderr: "/tmp/taskmaster.web.err"
    env:
      APP_ENV: "production"
      PORT: "8080"
    workingdir: "/tmp"
    umask: "022"

  worker:
    cmd: "python3 -c 'import time; time.sleep(99999)'"
    numprocs: 2
    autostart: true
    autorestart: true
    exitcodes: [0]
    starttime: 1
    startretries: 5
    stopsignal: TERM
    stoptime: 5
    stdout: "/tmp/taskmaster.worker.out"
    stderr: "/tmp/taskmaster.worker.err"
    env:
      WORKER_NAME: "alpha"
    workingdir: "/tmp"
    umask: "077"

  scheduler:
    cmd: "python3 -c 'import time; time.sleep(99999)'"
    numprocs: 1
    autostart: false
    autorestart: false
    exitcodes: [0]
    starttime: 1
    startretries: 0
    stopsignal: TERM
    stoptime: 5
    stdout: "/tmp/taskmaster.scheduler.out"
    stderr: "/tmp/taskmaster.scheduler.err"
    env:
      SCHEDULE: "*/5 * * * *"
    workingdir: "/tmp"
    umask: "022"
```

### Configuration Options

### Current Configuration Options

| Option | Type | Description | Status |
|--------|------|-------------|--------|
| `cmd` | string | Command to execute | ✅ |
| `autostart` | boolean | Start program on launch | ✅ |
| `autorestart` | boolean | Restart when exits | ✅ |
| `numprocs` | integer | Number of instances | ✅ |
| `exitcodes` | list | Expected exit codes | ✅ |
| `starttime` | integer | Seconds before "started" | ✅ |
| `startretries` | integer | Max restart attempts | ✅ |
| `stopsignal` | string | Signal for graceful stop | ✅ |
| `stoptime` | integer | Grace period before KILL | ✅ |
| `stdout` | string | Redirect stdout to file | ✅ |
| `stderr` | string | Redirect stderr to file | ✅ |
| `env` | dict | Environment variables | ✅ |
| `workingdir` | string | Working directory | ✅ |
| `umask` | string | File creation mask | ✅ |

### Target Configuration (from PDF)

```yaml
programs:
  nginx:
    cmd: "/usr/local/bin/nginx -c /etc/nginx/test.conf"
    numprocs: 1
    umask: 022
    workingdir: /tmp
    autostart: true
    autorestart: unexpected
    exitcodes:
      - 0
      - 2
    startretries: 3
    starttime: 5
    stopsignal: TERM
    stoptime: 10
    stdout: /tmp/nginx.stdout
    stderr: /tmp/nginx.stderr
    env:
      STARTED_BY: taskmaster
      ANSWER: 42
```

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
  web             ● Started            12345
  worker          ● Started            12346
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
  web             12345      ● RUNNING    python3 -m http.server 8080
  worker          12346      ● RUNNING    python3 -c 'import time; time.sleep(99999)'
────────────────────────────────────────────────────────────
  Total: 2 program(s)

taskmaster> stop web
Program 'web' stopped successfully.

taskmaster> reload
Configuration reloaded, Nothing Changed!

taskmaster> quit
Shutting down taskmaster...
```

## Log Format

Events are logged to `logs.log`:

```
▶ [2026-01-26 12:00:00] [web:1] [PID:12345] Started
▪ [2026-01-26 12:00:10] [web:1] [PID:12345] Stopped
↻ [2026-01-26 12:00:10] [web:1] Restarting
▶ [2026-01-26 12:00:11] [web:1] [PID:12350] Started
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
