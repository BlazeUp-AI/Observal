# `observal support`

Collect and inspect a **support bundle** — a compressed archive of local state
information that helps maintainers reproduce and diagnose bugs.

The bundle is entirely opt-in. Nothing is sent anywhere automatically; you
decide what to share and with whom.

---

## Subcommands

| Subcommand | Purpose |
|---|---|
| `observal support bundle` | Collect local state into a `.tar.gz` archive |
| `observal support inspect` | List and preview bundle contents before sharing |

---

## `observal support bundle`

```
observal support bundle [OPTIONS]
```

Gathers local diagnostic information and writes a `.tar.gz` archive to the
current working directory.

### What it collects

| Item | File inside bundle |
|---|---|
| Observal CLI version and Python version | `meta/versions.txt` |
| Active profile name and server URL (no credentials) | `meta/profile.txt` |
| `observal doctor` output (same checks, captured as text) | `meta/doctor.txt` |
| Sanitised CLI configuration (`~/.config/observal/config.toml`) | `config/config.toml` |
| Last 500 lines of the CLI log (`~/.local/share/observal/observal.log`) | `logs/cli.log` |
| OS name, architecture, and kernel version | `meta/system.txt` |
| Docker / Podman version, if present | `meta/docker.txt` |
| `observal telemetry status` output | `meta/telemetry.txt` |

### What is redacted

Before anything is written to the archive, the redaction pipeline in
[`observal_cli/support/redaction.py`](../../observal_cli/support/redaction.py)
strips or replaces the following patterns:

- API keys and bearer tokens (any value that matches the stored credential
  format, replaced with `[REDACTED]`)
- Passwords in connection strings (e.g. `postgresql://user:PASSWORD@…`
  becomes `postgresql://user:[REDACTED]@…`)
- Email addresses (replaced with `[REDACTED]`)
- Absolute home-directory paths (replaced with `~`)
- Any environment-variable value whose key contains `KEY`, `SECRET`,
  `PASSWORD`, `TOKEN`, or `CREDENTIAL`

If you are unsure what a bundle contains, run
[`observal support inspect`](#observal-support-inspect) before sharing it.

### Output location

The archive is written to the **current working directory**:

```
observal-support-<timestamp>.tar.gz
```

Example: `observal-support-20260512T143201.tar.gz`

To write to a different directory, pass `--output`:

```
observal support bundle --output /tmp/my-bundle.tar.gz
```

### Options

| Flag | Description |
|---|---|
| `--output PATH` | Override the output path (default: `./observal-support-<ts>.tar.gz`) |
| `--no-logs` | Exclude log files from the bundle |
| `--yes` / `-y` | Skip the confirmation prompt |

### Example

```
$ observal support bundle
Collecting support bundle…
  ✓ versions
  ✓ profile
  ✓ doctor
  ✓ config  (redacted)
  ✓ logs    (redacted, last 500 lines)
  ✓ system
  ✓ telemetry
Wrote observal-support-20260512T143201.tar.gz (14 KB)

Review contents before sharing:
  observal support inspect observal-support-20260512T143201.tar.gz
```

---

## `observal support inspect`

```
observal support inspect <BUNDLE_PATH> [OPTIONS]
```

Lists every file inside a support bundle and lets you preview individual
files so you can verify what the archive contains before attaching it to a
GitHub issue or sharing it in Discord.

### Usage

```
# List all files with sizes
observal support inspect observal-support-20260512T143201.tar.gz

# Preview a specific file
observal support inspect observal-support-20260512T143201.tar.gz --file logs/cli.log

# Show first N lines of a file (default 40)
observal support inspect observal-support-20260512T143201.tar.gz --file config/config.toml --lines 20
```

### Options

| Flag | Description |
|---|---|
| `--file PATH` | Print the contents of a specific file inside the bundle |
| `--lines N` | Limit preview to the first N lines (default: 40) |

### Example

```
$ observal support inspect observal-support-20260512T143201.tar.gz
Archive: observal-support-20260512T143201.tar.gz
  meta/versions.txt      312 B
  meta/profile.txt        84 B
  meta/doctor.txt        1.1 KB
  meta/system.txt        210 B
  meta/docker.txt         92 B
  meta/telemetry.txt     430 B
  config/config.toml      1.8 KB
  logs/cli.log           22.4 KB

$ observal support inspect observal-support-20260512T143201.tar.gz --file meta/profile.txt
--- meta/profile.txt ---
profile: default
server_url: http://localhost:8000
auth: [REDACTED]
```

---

## Privacy note

### What is **included**

- CLI and Python **version strings**
- Your configured **server URL** (host and port only — no credentials)
- **System metadata**: OS, architecture, kernel version, Docker version
- **Sanitised configuration**: `config.toml` with all secrets replaced by
  `[REDACTED]`
- **Truncated CLI logs**: the last 500 lines, with credentials and email
  addresses stripped

### What is **never included**

- API keys, passwords, or bearer tokens (always redacted)
- Email addresses (always redacted)
- The contents of your IDE configuration files (`.cursor/`, `.claude/`,
  `kiro/`, etc.)
- Telemetry data, trace payloads, or span contents
- Source code, agent configurations, or prompt templates
- Any file outside `~/.config/observal/` and `~/.local/share/observal/`

### Before you share

Run `observal support inspect <bundle>` to review the archive yourself.  
If you spot anything sensitive, delete the archive, run
`observal support bundle --no-logs`, and inspect again.

---

## See also

- [`observal doctor`](doctor.md) — check server connectivity and local health
- [`observal_cli/support/redaction.py`](../../observal_cli/support/redaction.py) — redaction implementation
