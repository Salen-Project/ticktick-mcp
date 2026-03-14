#!/usr/bin/env python3
"""
TickTick MCP Server

Provides tools to interact with TickTick task management via the official API.
Requires authentication via setup_auth.py before first use.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# --- Constants ---
API_BASE_URL = "https://api.ticktick.com/open/v1"
TOKEN_URL = "https://ticktick.com/oauth/token"
# Set via environment variables, or replace defaults with your own credentials
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

    # Return existing token if still valid (with 60s buffer)
    if time.time() < expires_at - 60:
        return tokens["access_token"]

    # Refresh the token
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


def _format_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Format a raw TickTick task dict into a clean response."""
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "content": task.get("content"),
        "due_date": _format_datetime(task.get("dueDate")),
        "priority": PRIORITY_MAP.get(task.get("priority", 0), "None"),
        "status": "Completed" if task.get("status") == 2 else "Active",
        "tags": task.get("tags", []),
        "project_id": task.get("projectId"),
    }


# --- Input Models ---

class CreateTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    title: str = Field(..., description="Task title (e.g., 'Buy groceries', 'Call dentist')", min_length=1, max_length=500)
    content: Optional[str] = Field(default=None, description="Task description or additional notes")
    due_date: Optional[str] = Field(default=None, description="Due date in ISO format (e.g., '2026-03-20') or with time (e.g., '2026-03-20T10:00:00+0000')")
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


# --- Tools ---

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

    Returns:
        str: JSON array of projects, each containing:
            - id (str): Project ID
            - name (str): Project name
            - color (str): Project color
            - closed (bool): Whether the project is archived

    Examples:
        - Use when: "What projects/lists do I have in TickTick?"
        - Use when: You need a project ID before creating or listing tasks
    """
    try:
        projects = await _make_request("GET", "project")
        result = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "color": p.get("color"),
                "closed": p.get("closed", False),
            }
            for p in projects
        ]
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


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

    Fetches all tasks for the given project ID. Use ticktick_list_projects
    first if you don't know the project ID.

    Args:
        params (ListTasksInput):
            - project_id (str): Project ID to list tasks from

    Returns:
        str: JSON array of tasks, each with id, title, content, due_date,
             priority, status, tags, and project_id.

    Examples:
        - Use when: "Show me my tasks in the Work project"
        - Use when: "What's on my to-do list?"
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
    """Create a new task in TickTick.

    Creates a task with the given title and optional details. If no project_id
    is provided, the task goes to the Inbox.

    Args:
        params (CreateTaskInput):
            - title (str): Task title (required)
            - content (Optional[str]): Notes or description
            - due_date (Optional[str]): Due date e.g. '2026-03-20' or '2026-03-20T10:00:00+0000'
            - priority (Optional[int]): 0=None, 1=Low, 3=Medium, 5=High (default: 0)
            - project_id (Optional[str]): Project ID. Uses Inbox if not set.
            - tags (Optional[List[str]]): Tag names to apply

    Returns:
        str: JSON with success status and created task details including its new ID.

    Examples:
        - "Add a task to buy groceries" -> title="Buy groceries"
        - "Remind me to call John tomorrow, high priority" -> title="Call John", priority=5, due_date="2026-03-15"
        - "Add 'Review report' to my Work project" -> use ticktick_list_projects first to get project_id
    """
    try:
        payload: Dict[str, Any] = {"title": params.title}

        if params.content:
            payload["content"] = params.content
        if params.due_date:
            payload["dueDate"] = _normalize_due_date(params.due_date)
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

    Args:
        params (GetTaskInput):
            - task_id (str): The task ID
            - project_id (str): The project ID the task belongs to

    Returns:
        str: JSON object with full task details including created and modified timestamps.

    Examples:
        - Use when: You have a task ID and need its current details
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

    Fetches the current task first, then applies your changes on top,
    so fields you don't specify are preserved.

    Args:
        params (UpdateTaskInput):
            - task_id (str): ID of the task to update (required)
            - project_id (str): Project ID the task belongs to (required)
            - title (Optional[str]): New task title
            - content (Optional[str]): New task description
            - due_date (Optional[str]): New due date (e.g., '2026-03-25')
            - priority (Optional[int]): New priority: 0=None, 1=Low, 3=Medium, 5=High

    Returns:
        str: JSON with success status and updated task details.

    Examples:
        - "Change the due date of task X to Friday"
        - "Make task Y high priority"
        - "Update the title of task Z"
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

    Args:
        params (TaskActionInput):
            - task_id (str): ID of the task to complete
            - project_id (str): ID of the project the task belongs to

    Returns:
        str: JSON success confirmation or error message.

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

    Args:
        params (TaskActionInput):
            - task_id (str): ID of the task to delete
            - project_id (str): ID of the project the task belongs to

    Returns:
        str: JSON success confirmation or error message.

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


if __name__ == "__main__":
    mcp.run()
