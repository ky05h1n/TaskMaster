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
- [x] `autorestart` - restart on exit (basic)
- [x] Detect new/changed/removed programs on reload
- [x] Handle removed programs on reload (stop & remove)

### 🔄 In Progress

### ❌ TODO

**Configuration Options:**
- [ ] `numprocs` - number of processes to start and keep running
- [ ] `autorestart: unexpected` - restart only on unexpected exits
- [ ] `exitcodes` - expected exit status codes
- [ ] `starttime` - time before considered "successfully started"
- [ ] `startretries` - max restart attempts before aborting
- [ ] `stopsignal` - signal to use for graceful stop (TERM, HUP, INT, etc.)
- [ ] `stoptime` - grace period before SIGKILL
- [ ] `stdout/stderr` - redirect to files (currently discarded)
- [ ] `env` - environment variables
- [ ] `workingdir` - working directory
- [ ] `umask` - file creation mask

**Features:**
- [ ] SIGHUP signal to reload configuration
- [ ] Proper signal handling (SIGTERM, SIGKILL for stop)

**Bonus Ideas:**
- [x] Client/server architecture (daemon + control program)
- [x] Email/HTTP/Syslog alerts (advanced logging)
- [ ] Attach/detach to process console (like tmux)

## Installation

```bash
git clone https://github.com/ky05h1n/TaskMaster.git
cd TaskMaster
pip install pyyaml
```

## Configuration

Edit `conf.yaml` to define your programs:

You can reference environment variables in `conf.yaml` with `${VAR}`. TaskMaster will load a local `.env` file (if present) and expand these values.

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

### Current Configuration Options

| Option | Type | Description | Status |
|--------|------|-------------|--------|
| `cmd` | string | Command to execute | ✅ |
| `autostart` | boolean | Start program on launch | ✅ |
| `autorestart` | boolean | Restart when exits | ✅ |
| `numprocs` | integer | Number of instances | ❌ |
| `exitcodes` | list | Expected exit codes | ❌ |
| `starttime` | integer | Seconds before "started" | ❌ |
| `startretries` | integer | Max restart attempts | ❌ |
| `stopsignal` | string | Signal for graceful stop | ❌ |
| `stoptime` | integer | Grace period before KILL | ❌ |
| `stdout` | string | Redirect stdout to file | ❌ |
| `stderr` | string | Redirect stderr to file | ❌ |
| `env` | dict | Environment variables | ❌ |
| `workingdir` | string | Working directory | ❌ |
| `umask` | string | File creation mask | ❌ |
| `user` | string | Run as user (Unix only) | ✅ (bonus) |
| `group` | string | Run as group (Unix only) | ✅ (bonus) |
| `alerts` | dict | Advanced logging/alerts | ✅ (bonus) |

### Target Configuration (from PDF)

```yaml
programs:
  nginx:
    cmd: "/usr/local/bin/nginx -c /etc/nginx/test.conf"
    user: nobody
    group: nogroup
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
alerts:
  email:
    enabled: false
    smtp_host: "smtp.example.com"
    smtp_port: 587
    username: "user@example.com"
    password: "app-password"
    from: "taskmaster@example.com"
    to:
      - "ops@example.com"
    subject: "TaskMaster Alert"
    use_tls: true
  http:
    enabled: false
    url: "https://hooks.example.com/taskmaster"
    method: "POST"
    headers:
      Authorization: "Bearer TOKEN"
    timeout: 5
  syslog:
    enabled: false
    address: "localhost"
    port: 514
    facility: "user"
```

## Usage

Start TaskMaster:

```bash
python3 TaskMaster.py
```

### Bonus: Client/Server Mode

Note: SMTP/HTTP/Syslog alerts and `user`/`group` (run-as) support are available only in the bonus server (client/server mode).

Run the daemon server (job control):

```bash
python3 bonus/server.py
```

If you start the server as root, it will only drop privileges when you explicitly set `TASKMASTER_RUN_AS_USER`:

```bash
TASKMASTER_RUN_AS_USER=youruser TASKMASTER_RUN_AS_GROUP=yourgroup sudo -E python3 bonus/server.py
```

To keep the server running as root (required to start programs as other users):

```bash
sudo python3 bonus/server.py
```

On Unix, the bonus server uses a local Unix socket and only allows root clients. Run the client with sudo:

```bash
sudo python3 bonus/client.py
```

#### Bonus: Attach/Detach Console

To allow attaching to a program console, set `console: true` on the program:

```yaml
programs:
  run_as_nobody:
    cmd: "sleep 60"
    autostart: false
    autorestart: false
    user: "nobody"
    group: "nogroup"
    console: true
```

Then attach from the client:

```text
attach run_as_nobody
```

Detach with `Ctrl-]` and the process continues in the background.

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

### Bonus: Web Dashboard

Run the daemon first, then the web dashboard:

```bash
pip install -r requirements.txt
sudo python3 bonus/server.py
python3 bonus/web_dashboard.py
```

Then open:

```
http://localhost:8000
```

The dashboard shows live status, CPU/memory, and allows start/stop/restart by talking to the daemon socket.

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
├── bonus/
│   ├── server.py     # Bonus daemon server
│   ├── client.py     # Bonus control shell client
│   └── __init__.py
├── conf.yaml        # Configuration file
├── logs.log         # Log file
└── README.md        # This file
```

## License

MIT License
