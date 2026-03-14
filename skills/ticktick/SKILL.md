---
name: ticktick
description: >
  AI-powered task management and productivity assistant. This skill activates
  whenever the user mentions a task, to-do, reminder, or something they need to do.
  Trigger phrases include "remind me to", "I need to", "don't let me forget",
  "add a task", "create a task", "what's on my list", "what's due today",
  "mark that as done", "complete the task", or any mention of capturing,
  organizing, or reviewing their tasks and to-dos.
version: 0.1.0
license: MIT
---

# TickTick Task Management Skill

Turn any conversation into action. This skill connects Claude to your TickTick
account so you can capture, review, and complete tasks just by talking.

## Available Tools

- `ticktick_create_task` — create a task (title, due date, priority, project, tags)
- `ticktick_list_projects` — list all projects/lists
- `ticktick_list_tasks` — list tasks in a project
- `ticktick_get_task` — get details of a specific task
- `ticktick_update_task` — update title, due date, priority
- `ticktick_complete_task` — mark a task as done
- `ticktick_delete_task` — permanently delete a task

## Behavior Guidelines

### Creating Tasks
- **Always create immediately** — don't ask for confirmation unless something is genuinely ambiguous
- **Parse natural language dates**: "tomorrow" → next day's date, "Friday" → upcoming Friday, "next week" → Monday of next week. Format as `YYYY-MM-DDT00:00:00+0000`
- **Infer priority from language**: "urgent", "important", "ASAP" → priority 5 (High); "when you get a chance" → priority 1 (Low); default → priority 0 (None)
- **Default to Inbox** if no project is mentioned (leave `project_id` empty)
- **If user mentions a project** (e.g., "add to Work"), call `ticktick_list_projects` first to find the ID, then create

### Listing Tasks
- If no project is specified, call `ticktick_list_projects` first, then show tasks across relevant projects
- Present tasks in a clean, readable format — not raw JSON

### Completing / Deleting Tasks
- For completing: call `ticktick_list_tasks` to find the task ID if needed, then `ticktick_complete_task`
- For deleting: confirm it's destructive if the user seems unsure, then delete

## Examples

User: "Remind me to call the dentist on Friday"
→ `ticktick_create_task` with title="Call the dentist", due_date set to upcoming Friday

User: "Add 'review Q1 report' to my Work project, high priority, due next Monday"
→ `ticktick_list_projects` to get Work project ID → `ticktick_create_task` with all fields

User: "What's on my plate today?"
→ `ticktick_list_projects` → `ticktick_list_tasks` for each relevant project → summarize clearly

User: "I finished the dentist task"
→ `ticktick_list_tasks` to find it → `ticktick_complete_task`
