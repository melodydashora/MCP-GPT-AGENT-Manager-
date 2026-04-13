"""
MCP Server - Eidolon agent proxied through Vecto.

Exposes secured git and file operations as MCP tools that any
MCP-compatible client can call. All operations go through:

    MCP Client -> MCP Server -> Vecto Proxy -> Eidolon Agent -> Git/FS
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Add parent to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import load_config

from .eidolon.agent import EidolonAgent
from .vecto.proxy import VectoProxy

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("mcp-agent-manager")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="repo_status",
        description="Get the current git repository status (branch, staged/unstaged changes).",
        inputSchema={
            "type": "object",
            "properties": {
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_pull",
        description="Pull latest changes from a remote repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin", "description": "Remote name"},
                "branch": {"type": "string", "description": "Branch to pull"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_fetch",
        description="Fetch refs from a remote without merging.",
        inputSchema={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin", "description": "Remote name"},
                "branch": {"type": "string", "description": "Branch to fetch"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_publish",
        description="Publish (push with upstream tracking) the current branch to a remote.",
        inputSchema={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin", "description": "Remote name"},
                "branch": {"type": "string", "description": "Branch to publish"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_push",
        description="Push commits to a remote repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin", "description": "Remote name"},
                "branch": {"type": "string", "description": "Branch to push"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_commit",
        description="Stage files and create a git commit.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
                "add_all": {"type": "boolean", "default": False, "description": "Stage all changes"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to stage",
                },
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["message"],
        },
    ),
    Tool(
        name="repo_diff",
        description="Show git diff of working tree or staged changes.",
        inputSchema={
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "default": False, "description": "Show staged changes only"},
                "path": {"type": "string", "description": "Limit diff to a specific path"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_log",
        description="Show recent commit log.",
        inputSchema={
            "type": "object",
            "properties": {
                "max_count": {"type": "integer", "default": 20, "description": "Max commits to show"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_branch",
        description="List, create, or delete git branches.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Branch name (for create/delete)"},
                "create": {"type": "boolean", "default": False, "description": "Create a new branch"},
                "delete": {"type": "boolean", "default": False, "description": "Delete a branch"},
                "list_all": {"type": "boolean", "default": False, "description": "List all branches including remote"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="repo_checkout",
        description="Checkout a branch or create and switch to a new one.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Branch or ref to checkout"},
                "create": {"type": "boolean", "default": False, "description": "Create the branch if it doesn't exist"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["target"],
        },
    ),
    Tool(
        name="repo_merge",
        description="Merge a branch into the current branch.",
        inputSchema={
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Branch to merge"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["branch"],
        },
    ),
    Tool(
        name="file_read",
        description="Read the contents of a file in the repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="file_write",
        description="Write content to a file in the repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "Content to write"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="file_list",
        description="List files in a directory with optional glob pattern.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": ".", "description": "Directory path"},
                "pattern": {"type": "string", "default": "*", "description": "Glob pattern"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
    Tool(
        name="file_search",
        description="Search for a text pattern across files in the repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text pattern to search for"},
                "glob": {"type": "string", "default": "**/*", "description": "File glob to limit search"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["pattern"],
        },
    ),
    Tool(
        name="audit_log",
        description="Retrieve the Vecto proxy audit log of recent operations.",
        inputSchema={
            "type": "object",
            "properties": {
                "last_n": {"type": "integer", "default": 50, "description": "Number of recent entries"},
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

def create_server(repo_path: Path | None = None) -> tuple[Server, VectoProxy]:
    """Create and configure the MCP server with Eidolon + Vecto."""
    cfg = load_config()

    if repo_path:
        effective_path = repo_path
    else:
        effective_path = cfg.repo_path

    # Initialize Eidolon agent
    agent = EidolonAgent(
        repo_path=effective_path,
        allowed_paths=cfg.eidolon.allowed_paths,
        allowed_operations=cfg.eidolon.allowed_operations,
        denied_patterns=cfg.eidolon.denied_patterns,
        auth_token=cfg.eidolon.auth_token,
        max_file_size_bytes=cfg.eidolon.max_file_size_bytes,
    )

    # Wrap in Vecto proxy
    proxy = VectoProxy(
        agent=agent,
        allowed_origins=cfg.vecto.allowed_origins,
        rate_limit_per_minute=60,
    )

    # Create MCP server
    app = Server(cfg.name)

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        # Special case: audit log doesn't go through Eidolon
        if name == "audit_log":
            last_n = arguments.get("last_n", 50)
            entries = proxy.get_audit_log(last_n)
            return [TextContent(type="text", text=json.dumps(entries, indent=2, default=str))]

        # All other tools go through Vecto -> Eidolon
        result = proxy.handle_request(
            tool_name=name,
            arguments=arguments,
            caller="mcp-client",
            origin="localhost",
        )

        if result.success:
            return [TextContent(type="text", text=result.output or "(no output)")]
        else:
            error_msg = f"Error: {result.error}"
            if result.output:
                error_msg += f"\nOutput: {result.output}"
            return [TextContent(type="text", text=error_msg)]

    return app, proxy


async def run_server() -> None:
    """Run the MCP server over stdio."""
    app, _ = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    """Entry point."""
    import asyncio
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
