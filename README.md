# TickTick MCP Server

A Model Context Protocol (MCP) server that connects Claude to your TickTick account, letting you create, list, update, and complete tasks just by talking.

<a href="https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/Salen-Project/ticktick-mcp/badge" alt="ticktick-mcp MCP server" />
</a>

## What it does

Once connected, you can say things like:
- *"Remind me to call the dentist on Friday"*
- *"Add a high priority task to review the Q1 report by Monday"*
- *"What's on my Work project list?"*
- *"Mark the grocery task as done"*

## Requirements

- Python 3.10+
- A TickTick account
- Claude (Cowork or Claude Code)

## Setup

### 1. Register a TickTick app

Go to [developer.ticktick.com](https://developer.ticktick.com), create a new app, and set:
- **App Service URL**: `http://localhost`
- **OAuth redirect URL**: `http://localhost:8080/callback`

Note your **Client ID** and **Client Secret**.

### 2. Add your credentials

Open `setup_auth.py` and `server.py` and replace the `CLIENT_ID` and `CLIENT_SECRET` values with your own.

### 3. Install and authenticate

```bash
cd ticktick-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 setup_auth.py
```

This opens your browser, asks you to authorize the app, and saves your tokens to `~/.ticktick_mcp/tokens.json`.

### 4. Register with Claude

```bash
claude mcp add ticktick -- /path/to/ticktick-mcp/.venv/bin/python3 /path/to/ticktick-mcp/server.py
```

Restart Claude/Cowork and you're done.

## Available Tools

| Tool | Description |
|------|-------------|
| `ticktick_list_projects` | List all your projects/lists |
| `ticktick_list_tasks` | List tasks in a project |
| `ticktick_create_task` | Create a new task |
| `ticktick_get_task` | Get details of a specific task |
| `ticktick_update_task` | Update title, due date, or priority |
| `ticktick_complete_task` | Mark a task as completed |
| `ticktick_delete_task` | Permanently delete a task |

## Notes

- Tokens are stored at `~/.ticktick_mcp/tokens.json` and refresh automatically
- The server uses TickTick's official OAuth 2.0 API (`https://api.ticktick.com/open/v1`)
- Token exchange uses HTTP Basic Auth — this is the format TickTick's API requires