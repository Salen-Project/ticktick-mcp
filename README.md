# TickTick MCP Server -- The Complete TickTick Integration for Claude

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/Salen-Project/ticktick-mcp/releases)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tools](https://img.shields.io/badge/tools-28-orange.svg)](#mcp-tools-reference)
[![Glama](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp/badge)](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp)

**28 tools. Full CRUD. Smart queries. Multi-condition filters. Batch operations. GTD support. Dida365 compatible.**

Connect Claude to your TickTick account and manage your entire task system through natural conversation -- create tasks, search across projects, check what's overdue, batch-create items, and stay organized without ever opening the app.

> "What's overdue?" --> Instantly shows all missed deadlines across every project.

---

## Why This One?

| Feature | This Server | TickTick Official MCP | jacepark12 |
|---|---|---|---|
| **Tools** | **28** | 22 | ~20 |
| **Multi-condition filter** | Yes (priority + tag + date + project) | Yes | No |
| **Move task between projects** | Yes | Yes | No |
| **Bulk complete** | Yes (up to 20) | Yes (up to 20) | No |
| **Batch update** | Yes | Yes | No |
| **Completed tasks view** | Yes | Yes | No |
| **Cross-project search** | Full text search | Yes | Yes |
| **Subtasks** | Yes | No | No |
| **GTD focus view** | Yes (high priority + due + overdue) | No | Partial |
| **Dida365 support** | Yes (configurable base URL) | No | Yes |
| **Async (httpx)** | Yes | N/A | No (sync requests) |
| **Pydantic validation** | Yes (typed inputs) | N/A | No |
| **MCP annotations** | Yes (readOnly, destructive hints) | N/A | No |
| **Self-hosted / open source** | Yes | No (hosted service) | Yes |
| **Privacy** | 100% local, your tokens only | Goes through TickTick servers | 100% local |

---

## Quick Start

### Prerequisites

- [TickTick](https://ticktick.com) account
- Python 3.10+
- [Claude Code](https://claude.ai/download) or Claude Desktop

### Step 1 -- Clone and install

```bash
git clone https://github.com/Salen-Project/ticktick-mcp
cd ticktick-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 2 -- Register a TickTick developer app

1. Go to [developer.ticktick.com](https://developer.ticktick.com)
2. Click **New App** and fill in any name
3. Set **OAuth Redirect URL** to: `http://localhost:8080/callback`
4. Copy your **Client ID** and **Client Secret**

### Step 3 -- Authenticate

```bash
TICKTICK_CLIENT_ID=your_id TICKTICK_CLIENT_SECRET=your_secret .venv/bin/python3 setup_auth.py
```

This opens your browser to authorize the app. Click **Allow** -- tokens are saved to `~/.ticktick_mcp/tokens.json` and refresh automatically.

### Step 4 -- Register with Claude Code

```bash
claude mcp add ticktick \
  -e TICKTICK_CLIENT_ID=your_id \
  -e TICKTICK_CLIENT_SECRET=your_secret \
  -- /path/to/ticktick-mcp/.venv/bin/python3 /path/to/ticktick-mcp/server.py
```

### For Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ticktick": {
      "type": "stdio",
      "command": "/path/to/ticktick-mcp/.venv/bin/python3",
      "args": ["/path/to/ticktick-mcp/server.py"],
      "env": {
        "TICKTICK_CLIENT_ID": "your_id",
        "TICKTICK_CLIENT_SECRET": "your_secret"
      }
    }
  }
}
```

### Step 5 -- Add the productivity skill (optional)

```bash
mkdir -p ~/.claude/skills/ticktick
cp skills/ticktick/SKILL.md ~/.claude/skills/ticktick/
```

---

## Dida365 Support

For Dida365 (TickTick's Chinese version), set these environment variables:

```bash
TICKTICK_BASE_URL=https://api.dida365.com/open/v1
TICKTICK_TOKEN_URL=https://dida365.com/oauth/token
```

---

## Usage Examples

| You say | What happens |
|---|---|
| "Remind me to call the dentist on Friday" | Task created with due date |
| "Add 'review Q1 report' to Work, high priority" | Task in Work project, priority 5 |
| "What's overdue?" | Shows all overdue tasks across projects |
| "What should I focus on?" | GTD view: high priority + due today + overdue |
| "Search for anything about 'budget'" | Full-text search across all projects |
| "Show me all high priority tasks" | Filters by priority=5 across projects |
| "What's due this week?" | Tasks due in the next 7 days |
| "Create tasks: buy milk, call John, submit report" | Batch creates 3 tasks |
| "Create a project called 'Vacation Planning'" | New project created |
| "Add subtask 'Buy sunscreen' under the vacation task" | Subtask created |
| "I finished the dentist task" | Task marked complete |
| "Delete the old Sprint project" | Project and all tasks deleted |

---

## MCP Tools Reference

### Projects (5 tools)

| Tool | Description |
|---|---|
| `ticktick_list_projects` | List all projects with IDs, names, colors |
| `ticktick_get_project` | Get details of a specific project |
| `ticktick_get_project_with_tasks` | Get project details + all undone tasks in one call |
| `ticktick_create_project` | Create a new project (name, color, view mode) |
| `ticktick_update_project` | Update a project's name, color, or view mode |
| `ticktick_delete_project` | Permanently delete a project |

### Tasks -- Basic CRUD (7 tools)

| Tool | Description |
|---|---|
| `ticktick_list_tasks` | List all tasks in a specific project |
| `ticktick_create_task` | Create a task (title, due date, priority, project, tags) |
| `ticktick_get_task` | Get full details of a specific task |
| `ticktick_update_task` | Update title, content, dates, or priority |
| `ticktick_complete_task` | Mark a task as completed |
| `ticktick_delete_task` | Permanently delete a task |
| `ticktick_create_subtask` | Create a subtask under a parent task |

### Tasks -- Smart Queries (7 tools)

| Tool | Description |
|---|---|
| `ticktick_get_all_tasks` | Get all tasks across all active projects |
| `ticktick_search_tasks` | Full-text search across titles, content, subtasks |
| `ticktick_get_tasks_by_priority` | Filter by priority (None/Low/Medium/High) |
| `ticktick_get_tasks_due_today` | Tasks due today across all projects |
| `ticktick_get_overdue_tasks` | All overdue tasks across all projects |
| `ticktick_get_tasks_due_this_week` | Tasks due within the next 7 days |
| `ticktick_get_tasks_due_in_days` | Tasks due in exactly N days |

### Tasks -- Batch & Productivity (5 tools)

| Tool | Description |
|---|---|
| `ticktick_batch_create_tasks` | Create multiple tasks at once |
| `ticktick_batch_update_tasks` | Update multiple tasks at once |
| `ticktick_complete_tasks_bulk` | Mark up to 20 tasks as completed at once |
| `ticktick_move_task` | Move a task from one project to another |
| `ticktick_get_focus_tasks` | GTD focus view: high priority + due today + overdue |

### Tasks -- Advanced Filters (2 tools)

| Tool | Description |
|---|---|
| `ticktick_filter_tasks` | Multi-condition filter: priority + tag + date range + project + status |
| `ticktick_get_completed_tasks` | View completed tasks in a project |

### User (1 tool)

| Tool | Description |
|---|---|
| `ticktick_get_user_preferences` | Get user settings (timezone, week start, etc.) |

---

## Architecture

```
server.py              # 20 MCP tools, async httpx, Pydantic validation
setup_auth.py          # One-time OAuth 2.0 setup (browser-based)
~/.ticktick_mcp/       # Token storage (auto-refreshed)
skills/ticktick/       # Claude skill for natural task language
```

**Design choices:**
- **Async everywhere** -- `httpx.AsyncClient` for non-blocking API calls
- **Pydantic input models** -- Type-safe, validated inputs with clear error messages
- **MCP annotations** -- `readOnlyHint`, `destructiveHint` for safer tool usage
- **Auto token refresh** -- Tokens refresh transparently with a 60-second buffer

---

## Troubleshooting

**"Given client ID does not match"** -- Double-check your Client ID on developer.ticktick.com.

**Port 8080 already in use** -- `lsof -ti:8080 | xargs kill -9` then retry.

**Tokens expired** -- Re-run `setup_auth.py` to get fresh tokens.

**Claude doesn't see tools** -- Run `claude mcp list` to verify registration.

---

## Contributing

Contributions welcome! Please open an issue first to discuss what you'd like to change.

```bash
git clone https://github.com/Salen-Project/ticktick-mcp
cd ticktick-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Make your changes to server.py
# Test: python3 -c "from server import mcp; print(len(mcp._tool_manager._tools), 'tools')"
```

---

## Links

- [GitHub](https://github.com/Salen-Project/ticktick-mcp)
- [Glama](https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp)
- [Report an issue](https://github.com/Salen-Project/ticktick-mcp/issues)
- [TickTick Developer Portal](https://developer.ticktick.com)
- [TickTick API Docs](https://developer.ticktick.com/api)

---

## License

MIT (c) [Salen-Project](https://github.com/Salen-Project)
