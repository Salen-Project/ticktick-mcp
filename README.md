# TickTick MCP Server — AI Task Management for Claude

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/Salen-Project/ticktick-mcp/releases)
[![Glama](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp/badge)](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp)

**Stop switching apps. Just talk.**

Connect Claude to your TickTick account and manage your entire task list through natural conversation — create tasks, check what's due, complete items, and stay organized without ever opening the TickTick app.

> "Remind me to call the dentist on Friday" → ✅ Task created in TickTick, instantly.

---

## What You Can Do

- **Capture tasks instantly** — say it out loud, Claude creates it in TickTick
- **Check your day** — "What's on my plate today?" gives a clean summary across all projects
- **Manage priorities** — Claude understands "urgent", "ASAP", "when you get a chance"
- **Natural due dates** — "next Monday", "end of month", "this Friday" all work
- **Organize by project** — add tasks to specific lists without touching the app
- **Mark things done** — "I finished the dentist task" → marked complete
- **Full CRUD** — create, read, update, complete, and delete tasks

---

## Installation

### Prerequisites

1. A [TickTick](https://ticktick.com) account
2. Python 3.10+
3. [Claude Code](https://claude.ai/download) or [Cowork](https://claude.ai/download)

### Step 1 — Clone and install dependencies

```bash
git clone https://github.com/Salen-Project/ticktick-mcp
cd ticktick-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 2 — Register a TickTick app

1. Go to [developer.ticktick.com](https://developer.ticktick.com)
2. Click **New App** → fill in any name
3. Set **OAuth Redirect URL** to: `http://localhost:8080/callback`
4. Copy your **Client ID** and **Client Secret**

### Step 3 — Authenticate

```bash
TICKTICK_CLIENT_ID=your_id TICKTICK_CLIENT_SECRET=your_secret .venv/bin/python3 setup_auth.py
```

This opens your browser to authorize the app. Click **Allow** — tokens are saved automatically to `~/.ticktick_mcp/tokens.json` and refresh in the background.

### Step 4 — Register with Claude Code

```bash
claude mcp add ticktick -- /path/to/ticktick-mcp/.venv/bin/python3 /path/to/ticktick-mcp/server.py
```

Replace `/path/to/ticktick-mcp` with the actual path (e.g. `$HOME/ticktick-mcp`).

### Step 5 — Add the productivity skill (optional but recommended)

Copy `skills/ticktick/SKILL.md` into your Claude skills folder so Claude automatically recognizes task language in any conversation:

```bash
mkdir -p ~/.claude/skills/ticktick
cp skills/ticktick/SKILL.md ~/.claude/skills/ticktick/
```

---

## Usage Examples

Once connected, just talk naturally:

| You say | What happens |
|---|---|
| "Remind me to call the dentist on Friday" | Task created with Friday due date |
| "Add 'review Q1 report' to my Work project, high priority" | Task added to Work list, priority High |
| "What's on my to-do list today?" | Summary of today's tasks across all projects |
| "I finished the dentist task" | Task marked complete |
| "What did I add this week?" | Lists recently created tasks |
| "Delete the dentist task" | Task permanently deleted |

---

## MCP Tools Reference

| Tool | Description |
|---|---|
| `ticktick_list_projects` | List all your TickTick projects/lists |
| `ticktick_list_tasks` | List tasks in a specific project |
| `ticktick_create_task` | Create a task with title, due date, priority, project |
| `ticktick_get_task` | Get full details of a specific task |
| `ticktick_update_task` | Update a task's title, due date, or priority |
| `ticktick_complete_task` | Mark a task as completed |
| `ticktick_delete_task` | Permanently delete a task |

---

## Install as a Cowork Plugin

This repo is structured as a Claude plugin. Add it in Cowork:

1. Open **Manage Plugins** → **Marketplaces** tab
2. Paste: `https://github.com/Salen-Project/ticktick-mcp`
3. Click **Add**

Or via Claude Code CLI:

```bash
claude plugins add Salen-Project/ticktick-mcp
```

The plugin includes the TickTick skill, which teaches Claude to automatically recognize task-related language in any conversation — no need to say "use TickTick" every time.

---

## Why This Over Other TickTick Integrations?

- ✅ **Official API** — uses TickTick's [open OAuth 2.0 API](https://developer.ticktick.com/), not unofficial endpoints
- ✅ **Automated OAuth** — one-command setup, tokens refresh automatically in the background
- ✅ **Cowork skill included** — Claude proactively recognizes task language without explicit prompting
- ✅ **Privacy-first** — runs 100% locally, your data never passes through a third-party server
- ✅ **Full CRUD** — not read-only; create, update, complete, and delete tasks

---

## Troubleshooting

**"Given client ID does not match"** — Double-check your Client ID on developer.ticktick.com. It's case-sensitive.

**Port 8080 already in use** — Run `lsof -ti:8080 | xargs kill -9` then retry `setup_auth.py`.

**Tokens expired** — Re-run `setup_auth.py` to get fresh tokens.

**Claude doesn't recognize TickTick commands** — Make sure the MCP is registered (`claude mcp list`) and the skill is installed.

---

## Links

- 🌐 [Glama listing](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp)
- 📦 [GitHub Releases](https://github.com/Salen-Project/ticktick-mcp/releases)
- 🐞 [Report an issue](https://github.com/Salen-Project/ticktick-mcp/issues)
- 🔑 [TickTick Developer Portal](https://developer.ticktick.com)

---

## License

MIT © [Salen-Project](https://github.com/Salen-Project)
