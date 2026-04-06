#!/usr/bin/env python3
"""
TickTick MCP Server

Provides tools to interact with TickTick task management via the official API.
Requires authentication via setup_auth.py before first use.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# --- Constants ---
API_BASE_URL = os.environ.get("TICKTICK_BASE_URL", "https://api.ticktick.com/open/v1")
TOKEN_URL = os.environ.get("TICKTICK_TOKEN_URL", "https://ticktick.com/oauth/token")
CLIENT_ID = os.environ.get("TICKTICK_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("TICKTICK_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
TOKENS_FILE = Path.home() / ".ticktick_mcp" / "tokens.json"

PRIORITY_MAP = {0: "None", 1: "Low", 3: "Medium", 5: "High"}

# --- MCP Server ---
mcp = FastMCP("ticktick_mcp")


# --- Token Management ---

def load_tokens() -> Dict[str, Any]:
    """Load OAuth tokens from disk."""
    if not TOKENS_FILE.exists():
        raise RuntimeError(
            "TickTick tokens not found. Please run 'python setup_auth.py' first to authenticate."
        )
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)


def save_tokens(tokens: Dict[str, Any]) -> None:
    """Save OAuth tokens to disk."""
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


async def get_access_token() -> str:
    """Get a valid access token, refreshing automatically if expired."""
    tokens = load_tokens()
    expires_at = tokens.get("expires_at", 0)

    if time.time() < expires_at - 60:
        return tokens["access_token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        new_tokens = response.json()
        new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
        save_tokens(new_tokens)
        return new_tokens["access_token"]


# --- Shared API Client ---

async def _make_request(method: str, endpoint: str, **kwargs) -> Any:
    """Make an authenticated API request to TickTick."""
    access_token = await get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            headers=headers,
            timeout=30.0,
            **kwargs,
        )
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}


def _handle_error(e: Exception) -> str:
    """Return clear, actionable error messages."""
    if isinstance(e, RuntimeError):
        return f"Error: {str(e)}"
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 401:
            return "Error: Authentication failed. Please run 'python setup_auth.py' to re-authenticate."
        if e.response.status_code == 403:
            return "Error: Permission denied. You may not have access to this resource."
        if e.response.status_code == 404:
            return "Error: Resource not found. Please check that the ID is correct."
        if e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please wait a moment before trying again."
        return f"Error: API request failed with status {e.response.status_code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    return f"Error: {type(e).__name__}: {str(e)}"


def _format_datetime(dt_str: Optional[str]) -> Optional[str]:
    """Format ISO datetime string to human-readable form."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def _normalize_due_date(due_date: str) -> str:
    """Ensure due date has time component for API compatibility."""
    if "T" not in due_date:
        return f"{due_date}T00:00:00+0000"
    return due_date


def _parse_task_date(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse a TickTick date string into a datetime object."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        except (ValueError, TypeError):
            return None


def _format_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Format a raw TickTick task dict into a clean response."""
    formatted = {
        "id": task.get("id"),
        "title": task.get("title"),
        "content": task.get("content"),
        "due_date": _format_datetime(task.get("dueDate")),
        "start_date": _format_datetime(task.get("startDate")),
        "priority": PRIORITY_MAP.get(task.get("priority", 0), "None"),
        "priority_value": task.get("priority", 0),
        "status": "Completed" if task.get("status") == 2 else "Active",
        "tags": task.get("tags", []),
        "project_id": task.get("projectId"),
    }
    items = task.get("items", [])
    if items:
        formatted["subtasks"] = [
            {
                "title": item.get("title"),
                "status": "Completed" if item.get("status") == 1 else "Active",
            }
            for item in items
        ]
    return formatted


# --- Input Models ---

class CreateTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    title: str = Field(..., description="Task title (e.g., 'Buy groceries', 'Call dentist')", min_length=1, max_length=500)
    content: Optional[str] = Field(default=None, description="Task description or additional notes")
    due_date: Optional[str] = Field(default=None, description="Due date in ISO format (e.g., '2026-03-20') or with time (e.g., '2026-03-20T10:00:00+0000')")
    start_date: Optional[str] = Field(default=None, description="Start date in ISO format")
    priority: Optional[int] = Field(default=0, description="Task priority: 0=None, 1=Low, 3=Medium, 5=High", ge=0, le=5)
    project_id: Optional[str] = Field(default=None, description="Project ID to add the task to. Leave empty to add to Inbox.")
    tags: Optional[List[str]] = Field(default=None, description="List of tag names to apply (e.g., ['work', 'urgent'])")


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    task_id: str = Field(..., description="ID of the task to update", min_length=1)
    project_id: str = Field(..., description="ID of the project the task belongs to", min_length=1)
    title: Optional[str] = Field(default=None, description="New task title")
    content: Optional[str] = Field(default=None, description="New task description")
    due_date: Optional[str] = Field(default=None, description="New due date (e.g., '2026-03-25' or '2026-03-25T09:00:00+0000')")
    start_date: Optional[str] = Field(default=None, description="New start date")
    priority: Optional[int] = Field(default=None, description="New priority: 0=None, 1=Low, 3=Medium, 5=High", ge=0, le=5)


class TaskActionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    task_id: str = Field(..., description="ID of the task", min_length=1)
    project_id: str = Field(..., description="ID of the project the task belongs to", min_length=1)


class GetTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    task_id: str = Field(..., description="Task ID to retrieve", min_length=1)
    project_id: str = Field(..., description="Project ID the task belongs to", min_length=1)


class ListTasksInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    project_id: str = Field(..., description="Project ID to list tasks from", min_length=1)


class CreateProjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    name: str = Field(..., description="Project name", min_length=1, max_length=200)
    color: Optional[str] = Field(default=None, description="Color hex code (e.g., '#F18181')")
    view_mode: Optional[str] = Field(default="list", description="View mode: 'list', 'kanban', or 'timeline'")


class ProjectIdInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    project_id: str = Field(..., description="ID of the project", min_length=1)


class SearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    query: str = Field(..., description="Search text (case-insensitive, matches title, content, and subtasks)", min_length=1)


class PriorityFilterInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    priority: int = Field(..., description="Priority to filter by: 0=None, 1=Low, 3=Medium, 5=High")


class DaysInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    days: int = Field(..., description="Number of days from today (0=today, 1=tomorrow, 7=next week)", ge=0)


class BatchCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    tasks: List[Dict[str, Any]] = Field(
        ...,
        description="List of task objects. Each must have 'title' (str). Optional: 'project_id', 'content', 'due_date', 'start_date', 'priority', 'tags'.",
        min_length=1,
    )


class CreateSubtaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    title: str = Field(..., description="Subtask title", min_length=1)
    parent_task_id: str = Field(..., description="ID of the parent task", min_length=1)
    project_id: str = Field(..., description="Project ID (must match parent task's project)", min_length=1)
    content: Optional[str] = Field(default=None, description="Subtask description")
    priority: Optional[int] = Field(default=0, description="Priority: 0=None, 1=Low, 3=Medium, 5=High", ge=0, le=5)


class MoveTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    task_id: str = Field(..., description="ID of the task to move", min_length=1)
    source_project_id: str = Field(..., description="Current project ID the task belongs to", min_length=1)
    target_project_id: str = Field(..., description="Destination project ID to move the task to", min_length=1)


class BulkCompleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    project_id: str = Field(..., description="Project ID containing the tasks", min_length=1)
    task_ids: List[str] = Field(..., description="List of task IDs to mark as completed (max 20)", min_length=1, max_length=20)


class BatchUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    tasks: List[Dict[str, Any]] = Field(
        ...,
        description="List of task update objects. Each must have 'task_id' and 'project_id'. Optional: 'title', 'content', 'due_date', 'start_date', 'priority'.",
        min_length=1,
    )


class FilterTasksInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    priority: Optional[int] = Field(default=None, description="Filter by priority: 0=None, 1=Low, 3=Medium, 5=High")
    project_id: Optional[str] = Field(default=None, description="Filter to a specific project")
    tag: Optional[str] = Field(default=None, description="Filter by tag name")
    due_before: Optional[str] = Field(default=None, description="Only tasks due before this date (ISO format, e.g. '2026-04-15')")
    due_after: Optional[str] = Field(default=None, description="Only tasks due after this date (ISO format)")
    status: Optional[str] = Field(default="active", description="'active' (default) or 'all' to include completed")


class CompletedTasksInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    project_id: str = Field(..., description="Project ID to list completed tasks from", min_length=1)


# --- Helper: cross-project task filtering ---

async def _get_all_tasks_filtered(filter_fn=None) -> List[Dict[str, Any]]:
    """Fetch all tasks across all active projects, optionally filtering."""
    projects = await _make_request("GET", "project")
    all_tasks = []
    for project in projects:
        if project.get("closed"):
            continue
        try:
            data = await _make_request("GET", f"project/{project['id']}/data")
            for task in data.get("tasks", []):
                task["_project_name"] = project.get("name", "Unknown")
                if filter_fn is None or filter_fn(task):
                    all_tasks.append(task)
        except Exception:
            continue
    return all_tasks


# =====================
# TOOLS: Projects (4)
# =====================

@mcp.tool(
    name="ticktick_list_projects",
    annotations={
        "title": "List TickTick Projects",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_list_projects() -> str:
    """List all TickTick projects (task lists) in the user's account.

    Returns all projects with their IDs and names. Use the project ID
    with other tools to create or list tasks in a specific project.

    Examples:
        - "What projects do I have in TickTick?"
        - "Show me my task lists"
    """
    try:
        projects = await _make_request("GET", "project")
        result = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "color": p.get("color"),
                "view_mode": p.get("viewMode"),
                "kind": p.get("kind"),
                "closed": p.get("closed", False),
            }
            for p in projects
        ]
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_project",
    annotations={
        "title": "Get Project Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_project(params: ProjectIdInput) -> str:
    """Get details of a specific TickTick project by ID.

    Examples:
        - "Show me details of my Work project"
    """
    try:
        project = await _make_request("GET", f"project/{params.project_id}")
        return json.dumps({
            "id": project.get("id"),
            "name": project.get("name"),
            "color": project.get("color"),
            "view_mode": project.get("viewMode"),
            "kind": project.get("kind"),
            "closed": project.get("closed", False),
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_create_project",
    annotations={
        "title": "Create a TickTick Project",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_create_project(params: CreateProjectInput) -> str:
    """Create a new project (task list) in TickTick.

    Examples:
        - "Create a new project called 'Vacation Planning'"
        - "Make a new kanban board called 'Sprint 12'"
    """
    try:
        payload: Dict[str, Any] = {"name": params.name, "kind": "TASK"}
        if params.color:
            payload["color"] = params.color
        if params.view_mode:
            payload["viewMode"] = params.view_mode

        project = await _make_request("POST", "project", json=payload)
        return json.dumps({"success": True, "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "color": project.get("color"),
        }}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_delete_project",
    annotations={
        "title": "Delete a TickTick Project",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_delete_project(params: ProjectIdInput) -> str:
    """Permanently delete a TickTick project and all its tasks. Cannot be undone.

    Examples:
        - "Delete the old Sprint 10 project"
    """
    try:
        await _make_request("DELETE", f"project/{params.project_id}")
        return json.dumps({"success": True, "message": f"Project '{params.project_id}' deleted."})
    except Exception as e:
        return _handle_error(e)


# =====================
# TOOLS: Basic Tasks (7)
# =====================

@mcp.tool(
    name="ticktick_list_tasks",
    annotations={
        "title": "List Tasks in a Project",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_list_tasks(params: ListTasksInput) -> str:
    """List all active tasks in a specific TickTick project.

    Examples:
        - "Show me my tasks in the Work project"
        - "What's on my to-do list?"
    """
    try:
        data = await _make_request("GET", f"project/{params.project_id}/data")
        tasks = data.get("tasks", [])
        result = [_format_task(t) for t in tasks]
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_create_task",
    annotations={
        "title": "Create a TickTick Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_create_task(params: CreateTaskInput) -> str:
    """Create a new task in TickTick. If no project_id is provided, the task goes to Inbox.

    Examples:
        - "Add a task to buy groceries"
        - "Remind me to call John tomorrow, high priority"
        - "Add 'Review report' to my Work project"
    """
    try:
        payload: Dict[str, Any] = {"title": params.title}

        if params.content:
            payload["content"] = params.content
        if params.due_date:
            payload["dueDate"] = _normalize_due_date(params.due_date)
        if params.start_date:
            payload["startDate"] = _normalize_due_date(params.start_date)
        if params.priority is not None:
            payload["priority"] = params.priority
        if params.project_id:
            payload["projectId"] = params.project_id
        if params.tags:
            payload["tags"] = params.tags

        task = await _make_request("POST", "task", json=payload)
        return json.dumps({"success": True, "task": _format_task(task)}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_task",
    annotations={
        "title": "Get a TickTick Task",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_task(params: GetTaskInput) -> str:
    """Get full details of a specific TickTick task by ID.

    Examples:
        - "Show me the details of that task"
    """
    try:
        task = await _make_request("GET", f"project/{params.project_id}/task/{params.task_id}")
        result = _format_task(task)
        result["created_time"] = _format_datetime(task.get("createdTime"))
        result["modified_time"] = _format_datetime(task.get("modifiedTime"))
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_update_task",
    annotations={
        "title": "Update a TickTick Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_update_task(params: UpdateTaskInput) -> str:
    """Update an existing TickTick task. Only provided fields are changed.

    Examples:
        - "Change the due date of task X to Friday"
        - "Make task Y high priority"
    """
    try:
        current = await _make_request("GET", f"project/{params.project_id}/task/{params.task_id}")

        payload: Dict[str, Any] = {
            "id": params.task_id,
            "projectId": params.project_id,
            "title": params.title if params.title is not None else current.get("title"),
            "content": params.content if params.content is not None else current.get("content"),
            "priority": params.priority if params.priority is not None else current.get("priority", 0),
        }

        if params.due_date is not None:
            payload["dueDate"] = _normalize_due_date(params.due_date)
        elif current.get("dueDate"):
            payload["dueDate"] = current.get("dueDate")

        if params.start_date is not None:
            payload["startDate"] = _normalize_due_date(params.start_date)
        elif current.get("startDate"):
            payload["startDate"] = current.get("startDate")

        task = await _make_request("POST", f"task/{params.task_id}", json=payload)
        return json.dumps({"success": True, "task": _format_task(task)}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_complete_task",
    annotations={
        "title": "Complete a TickTick Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_complete_task(params: TaskActionInput) -> str:
    """Mark a TickTick task as completed.

    Examples:
        - "Mark the grocery task as done"
        - "Complete task X"
    """
    try:
        await _make_request(
            "POST", f"project/{params.project_id}/task/{params.task_id}/complete"
        )
        return json.dumps({"success": True, "message": f"Task '{params.task_id}' marked as completed."})
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_delete_task",
    annotations={
        "title": "Delete a TickTick Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_delete_task(params: TaskActionInput) -> str:
    """Permanently delete a TickTick task. This action cannot be undone.

    Examples:
        - "Delete the grocery task"
        - "Remove task X permanently"
    """
    try:
        await _make_request(
            "DELETE", f"project/{params.project_id}/task/{params.task_id}"
        )
        return json.dumps({"success": True, "message": f"Task '{params.task_id}' has been deleted."})
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_create_subtask",
    annotations={
        "title": "Create a Subtask",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_create_subtask(params: CreateSubtaskInput) -> str:
    """Create a subtask under an existing parent task.

    Examples:
        - "Add a subtask 'Buy milk' under the grocery task"
    """
    try:
        payload: Dict[str, Any] = {
            "title": params.title,
            "projectId": params.project_id,
            "parentId": params.parent_task_id,
        }
        if params.content:
            payload["content"] = params.content
        if params.priority is not None:
            payload["priority"] = params.priority

        task = await _make_request("POST", "task", json=payload)
        return json.dumps({"success": True, "subtask": _format_task(task)}, indent=2)
    except Exception as e:
        return _handle_error(e)


# =====================
# TOOLS: Smart Queries (7)
# =====================

@mcp.tool(
    name="ticktick_get_all_tasks",
    annotations={
        "title": "Get All Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_all_tasks() -> str:
    """Get all active tasks across all projects. Skips archived projects.

    Examples:
        - "Show me everything on my plate"
        - "What are all my tasks?"
    """
    try:
        tasks = await _get_all_tasks_filtered()
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({"count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_search_tasks",
    annotations={
        "title": "Search Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_search_tasks(params: SearchInput) -> str:
    """Search for tasks by title, content, or subtask titles across all projects.

    Examples:
        - "Search for tasks about 'dentist'"
        - "Find anything related to 'report'"
    """
    try:
        query_lower = params.query.lower()

        def matches(task: Dict[str, Any]) -> bool:
            if query_lower in task.get("title", "").lower():
                return True
            if query_lower in task.get("content", "").lower():
                return True
            for item in task.get("items", []):
                if query_lower in item.get("title", "").lower():
                    return True
            return False

        tasks = await _get_all_tasks_filtered(filter_fn=matches)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({"query": params.query, "count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_tasks_by_priority",
    annotations={
        "title": "Filter Tasks by Priority",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_tasks_by_priority(params: PriorityFilterInput) -> str:
    """Get all tasks with a specific priority level across all projects.

    Examples:
        - "Show me all high priority tasks" (priority=5)
        - "What's marked as medium priority?" (priority=3)
    """
    try:
        if params.priority not in PRIORITY_MAP:
            return json.dumps({"error": f"Invalid priority. Valid values: {list(PRIORITY_MAP.keys())}"})

        tasks = await _get_all_tasks_filtered(
            filter_fn=lambda t: t.get("priority", 0) == params.priority
        )
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        label = PRIORITY_MAP[params.priority]
        return json.dumps({"priority": label, "count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_tasks_due_today",
    annotations={
        "title": "Tasks Due Today",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_tasks_due_today() -> str:
    """Get all tasks that are due today across all projects.

    Examples:
        - "What's due today?"
        - "What do I need to do today?"
    """
    try:
        today = datetime.now(timezone.utc).date()

        def is_due_today(task: Dict[str, Any]) -> bool:
            dt = _parse_task_date(task.get("dueDate"))
            return dt is not None and dt.date() == today

        tasks = await _get_all_tasks_filtered(filter_fn=is_due_today)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({"date": str(today), "count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_overdue_tasks",
    annotations={
        "title": "Overdue Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_overdue_tasks() -> str:
    """Get all overdue tasks across all projects.

    Examples:
        - "What's overdue?"
        - "Show me tasks I've missed"
    """
    try:
        now = datetime.now(timezone.utc)

        def is_overdue(task: Dict[str, Any]) -> bool:
            dt = _parse_task_date(task.get("dueDate"))
            return dt is not None and dt < now and task.get("status") != 2

        tasks = await _get_all_tasks_filtered(filter_fn=is_overdue)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({"count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_tasks_due_this_week",
    annotations={
        "title": "Tasks Due This Week",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_tasks_due_this_week() -> str:
    """Get all tasks due within the next 7 days across all projects.

    Examples:
        - "What's due this week?"
        - "Show me my week ahead"
    """
    try:
        today = datetime.now(timezone.utc).date()
        week_end = today + timedelta(days=7)

        def is_due_this_week(task: Dict[str, Any]) -> bool:
            dt = _parse_task_date(task.get("dueDate"))
            return dt is not None and today <= dt.date() <= week_end

        tasks = await _get_all_tasks_filtered(filter_fn=is_due_this_week)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({
            "from": str(today),
            "to": str(week_end),
            "count": len(result),
            "tasks": result,
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_tasks_due_in_days",
    annotations={
        "title": "Tasks Due in N Days",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_tasks_due_in_days(params: DaysInput) -> str:
    """Get all tasks due in exactly N days from today.

    Examples:
        - "What's due tomorrow?" (days=1)
        - "What's due in 3 days?" (days=3)
    """
    try:
        target = (datetime.now(timezone.utc) + timedelta(days=params.days)).date()

        def is_due_on_target(task: Dict[str, Any]) -> bool:
            dt = _parse_task_date(task.get("dueDate"))
            return dt is not None and dt.date() == target

        tasks = await _get_all_tasks_filtered(filter_fn=is_due_on_target)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        label = "today" if params.days == 0 else f"in {params.days} day{'s' if params.days != 1 else ''}"
        return json.dumps({"due": label, "date": str(target), "count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


# =====================
# TOOLS: Batch & GTD (2)
# =====================

@mcp.tool(
    name="ticktick_batch_create_tasks",
    annotations={
        "title": "Batch Create Tasks",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ticktick_batch_create_tasks(params: BatchCreateInput) -> str:
    """Create multiple tasks at once. Each task must have a 'title'. Optional fields:
    'project_id', 'content', 'due_date', 'start_date', 'priority', 'tags'.

    Examples:
        - "Create tasks: buy milk, call dentist, submit report"
    """
    try:
        created = []
        failed = []

        for i, task_data in enumerate(params.tasks):
            try:
                payload: Dict[str, Any] = {"title": task_data["title"]}
                if task_data.get("project_id"):
                    payload["projectId"] = task_data["project_id"]
                if task_data.get("content"):
                    payload["content"] = task_data["content"]
                if task_data.get("due_date"):
                    payload["dueDate"] = _normalize_due_date(task_data["due_date"])
                if task_data.get("start_date"):
                    payload["startDate"] = _normalize_due_date(task_data["start_date"])
                if task_data.get("priority") is not None:
                    payload["priority"] = task_data["priority"]
                if task_data.get("tags"):
                    payload["tags"] = task_data["tags"]

                task = await _make_request("POST", "task", json=payload)
                created.append({"index": i + 1, "title": task_data["title"], "id": task.get("id")})
            except Exception as ex:
                failed.append({"index": i + 1, "title": task_data.get("title", "?"), "error": str(ex)})

        return json.dumps({
            "created": len(created),
            "failed": len(failed),
            "results": created,
            "errors": failed,
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_focus_tasks",
    annotations={
        "title": "Get Focus Tasks (GTD)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_focus_tasks() -> str:
    """Get tasks that need immediate attention: high priority (5), due today, or overdue.
    Useful for a GTD-style 'what should I work on now?' view.

    Examples:
        - "What should I focus on right now?"
        - "What's urgent?"
    """
    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        def needs_focus(task: Dict[str, Any]) -> bool:
            if task.get("status") == 2:
                return False
            if task.get("priority", 0) == 5:
                return True
            dt = _parse_task_date(task.get("dueDate"))
            if dt is not None and dt.date() <= today:
                return True
            return False

        tasks = await _get_all_tasks_filtered(filter_fn=needs_focus)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        return json.dumps({"count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


# =====================
# TOOLS: Advanced (5)
# =====================

@mcp.tool(
    name="ticktick_move_task",
    annotations={
        "title": "Move Task to Another Project",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_move_task(params: MoveTaskInput) -> str:
    """Move a task from one project to another.

    Examples:
        - "Move the dentist task to my Personal project"
    """
    try:
        current = await _make_request("GET", f"project/{params.source_project_id}/task/{params.task_id}")
        payload = {
            "id": params.task_id,
            "projectId": params.target_project_id,
            "title": current.get("title"),
            "content": current.get("content"),
            "priority": current.get("priority", 0),
        }
        if current.get("dueDate"):
            payload["dueDate"] = current["dueDate"]
        if current.get("startDate"):
            payload["startDate"] = current["startDate"]
        if current.get("tags"):
            payload["tags"] = current["tags"]

        task = await _make_request("POST", f"task/{params.task_id}", json=payload)
        return json.dumps({"success": True, "task": _format_task(task)}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_complete_tasks_bulk",
    annotations={
        "title": "Bulk Complete Tasks",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_complete_tasks_bulk(params: BulkCompleteInput) -> str:
    """Mark multiple tasks in the same project as completed at once (max 20).

    Examples:
        - "Complete all the grocery tasks"
    """
    try:
        completed = []
        failed = []
        for task_id in params.task_ids:
            try:
                await _make_request(
                    "POST", f"project/{params.project_id}/task/{task_id}/complete"
                )
                completed.append(task_id)
            except Exception as ex:
                failed.append({"task_id": task_id, "error": str(ex)})

        return json.dumps({
            "completed": len(completed),
            "failed": len(failed),
            "completed_ids": completed,
            "errors": failed,
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_batch_update_tasks",
    annotations={
        "title": "Batch Update Tasks",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_batch_update_tasks(params: BatchUpdateInput) -> str:
    """Update multiple tasks at once. Each task object must have 'task_id' and 'project_id'.

    Examples:
        - "Set all these tasks to high priority"
        - "Push the due date of these 3 tasks to next Monday"
    """
    try:
        updated = []
        failed = []

        for i, task_data in enumerate(params.tasks):
            try:
                task_id = task_data["task_id"]
                project_id = task_data["project_id"]
                current = await _make_request("GET", f"project/{project_id}/task/{task_id}")

                payload: Dict[str, Any] = {
                    "id": task_id,
                    "projectId": project_id,
                    "title": task_data.get("title", current.get("title")),
                    "content": task_data.get("content", current.get("content")),
                    "priority": task_data.get("priority", current.get("priority", 0)),
                }
                if task_data.get("due_date"):
                    payload["dueDate"] = _normalize_due_date(task_data["due_date"])
                elif current.get("dueDate"):
                    payload["dueDate"] = current["dueDate"]
                if task_data.get("start_date"):
                    payload["startDate"] = _normalize_due_date(task_data["start_date"])
                elif current.get("startDate"):
                    payload["startDate"] = current["startDate"]

                task = await _make_request("POST", f"task/{task_id}", json=payload)
                updated.append({"index": i + 1, "task_id": task_id, "title": task.get("title")})
            except Exception as ex:
                failed.append({"index": i + 1, "task_id": task_data.get("task_id", "?"), "error": str(ex)})

        return json.dumps({
            "updated": len(updated),
            "failed": len(failed),
            "results": updated,
            "errors": failed,
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_filter_tasks",
    annotations={
        "title": "Filter Tasks (Multi-Condition)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_filter_tasks(params: FilterTasksInput) -> str:
    """Filter tasks across projects by multiple conditions at once: priority, tag,
    due date range, project, and status. All filters are optional and combined with AND logic.

    Examples:
        - "Show high priority tasks due before Friday"
        - "Find all tasks tagged 'work' that are overdue"
        - "List medium priority tasks in my Personal project"
    """
    try:
        def matches(task: Dict[str, Any]) -> bool:
            if params.status == "active" and task.get("status") == 2:
                return False
            if params.priority is not None and task.get("priority", 0) != params.priority:
                return False
            if params.tag is not None and params.tag not in task.get("tags", []):
                return False
            if params.project_id is not None and task.get("projectId") != params.project_id:
                return False
            if params.due_before or params.due_after:
                dt = _parse_task_date(task.get("dueDate"))
                if dt is None:
                    return False
                if params.due_before:
                    cutoff = datetime.fromisoformat(params.due_before.replace("Z", "+00:00"))
                    if dt.date() > cutoff.date():
                        return False
                if params.due_after:
                    cutoff = datetime.fromisoformat(params.due_after.replace("Z", "+00:00"))
                    if dt.date() < cutoff.date():
                        return False
            return True

        tasks = await _get_all_tasks_filtered(filter_fn=matches)
        result = [_format_task(t) | {"project_name": t.get("_project_name")} for t in tasks]
        filters_applied = {k: v for k, v in params.model_dump().items() if v is not None}
        return json.dumps({"filters": filters_applied, "count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_completed_tasks",
    annotations={
        "title": "Get Completed Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_completed_tasks(params: CompletedTasksInput) -> str:
    """Get completed tasks from a specific project. Useful for reviewing what you've accomplished.

    Examples:
        - "What did I complete in my Work project?"
        - "Show me finished tasks"
    """
    try:
        data = await _make_request("GET", f"project/{params.project_id}/data")
        tasks = data.get("tasks", [])
        completed = [t for t in tasks if t.get("status") == 2]
        result = [_format_task(t) for t in completed]
        return json.dumps({"count": len(result), "tasks": result}, indent=2)
    except Exception as e:
        return _handle_error(e)


# =====================
# TOOLS: Parity with Official MCP (3)
# =====================

@mcp.tool(
    name="ticktick_update_project",
    annotations={
        "title": "Update a TickTick Project",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_update_project(params: ProjectIdInput, name: Optional[str] = None, color: Optional[str] = None, view_mode: Optional[str] = None) -> str:
    """Update a project's name, color, or view mode.

    Examples:
        - "Rename my Work project to 'Work 2026'"
        - "Change the project color to blue"
    """
    try:
        current = await _make_request("GET", f"project/{params.project_id}")
        payload: Dict[str, Any] = {
            "id": params.project_id,
            "name": name if name else current.get("name"),
        }
        if color:
            payload["color"] = color
        if view_mode:
            payload["viewMode"] = view_mode

        project = await _make_request("POST", f"project/{params.project_id}", json=payload)
        return json.dumps({"success": True, "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "color": project.get("color"),
        }}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_project_with_tasks",
    annotations={
        "title": "Get Project with All Undone Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_project_with_tasks(params: ProjectIdInput) -> str:
    """Get a project's details together with all its undone tasks in one call.

    Examples:
        - "Show me my Work project and everything in it"
    """
    try:
        data = await _make_request("GET", f"project/{params.project_id}/data")
        project_info = data.get("project", {})
        tasks = [t for t in data.get("tasks", []) if t.get("status") != 2]
        return json.dumps({
            "project": {
                "id": project_info.get("id"),
                "name": project_info.get("name"),
                "color": project_info.get("color"),
            },
            "task_count": len(tasks),
            "tasks": [_format_task(t) for t in tasks],
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="ticktick_get_user_preferences",
    annotations={
        "title": "Get User Preferences",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ticktick_get_user_preferences() -> str:
    """Get the current user's TickTick preferences and settings (timezone, week start, etc.).

    Examples:
        - "What timezone is my TickTick set to?"
    """
    try:
        prefs = await _make_request("GET", "user/preferences")
        return json.dumps(prefs, indent=2)
    except Exception as e:
        return _handle_error(e)


if __name__ == "__main__":
    mcp.run()
