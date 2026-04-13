"""
Vecto Router - Routes incoming MCP tool calls to the appropriate Eidolon agent method.

The router maps tool names to agent operations and handles parameter
validation and result formatting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from ..eidolon.agent import EidolonAgent
from ..eidolon.operations import OpResult

logger = logging.getLogger("vecto.router")


@dataclass
class Route:
    """A single route mapping a tool name to an agent method."""
    tool_name: str
    handler: Callable[..., OpResult]
    description: str


class VectoRouter:
    """
    Routes MCP tool calls through to Eidolon agent methods.

    Each route maps a tool name (e.g., "repo_publish") to the corresponding
    EidolonAgent method, handling parameter extraction and result formatting.
    """

    def __init__(self, agent: EidolonAgent):
        self.agent = agent
        self._routes: dict[str, Route] = {}
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all available routes from the Eidolon agent."""
        routes = [
            Route("repo_status", self.agent.status, "Get repository status"),
            Route("repo_pull", self.agent.pull, "Pull from remote"),
            Route("repo_fetch", self.agent.fetch, "Fetch from remote"),
            Route("repo_publish", self.agent.publish, "Publish (push) to remote"),
            Route("repo_push", self.agent.push, "Push to remote"),
            Route("repo_commit", self.agent.commit, "Stage and commit changes"),
            Route("repo_diff", self.agent.diff, "Show diff"),
            Route("repo_log", self.agent.log, "Show commit log"),
            Route("repo_branch", self.agent.branch, "Branch operations"),
            Route("repo_checkout", self.agent.checkout, "Checkout branch"),
            Route("repo_merge", self.agent.merge, "Merge branch"),
            Route("file_read", self.agent.read_file, "Read a file"),
            Route("file_write", self.agent.write_file, "Write a file"),
            Route("file_list", self.agent.list_files, "List files"),
            Route("file_search", self.agent.search, "Search file contents"),
        ]
        for route in routes:
            self._routes[route.tool_name] = route
            logger.debug("Registered route: %s -> %s", route.tool_name, route.description)

    def list_routes(self) -> list[dict[str, str]]:
        """List all available routes."""
        return [
            {"tool": r.tool_name, "description": r.description}
            for r in self._routes.values()
        ]

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> OpResult:
        """
        Dispatch a tool call to the appropriate Eidolon agent method.

        Extracts the auth token from arguments (if present) and passes
        remaining arguments to the handler.
        """
        route = self._routes.get(tool_name)
        if route is None:
            return OpResult(
                success=False,
                output="",
                error=f"Unknown tool: '{tool_name}'. Available: {sorted(self._routes.keys())}",
            )

        # Extract token from arguments for auth
        token = arguments.pop("auth_token", None)
        arguments["token"] = token

        try:
            result = route.handler(**arguments)
            logger.info("Dispatched %s -> success=%s", tool_name, result.success)
            return result
        except TypeError as exc:
            return OpResult(
                success=False,
                output="",
                error=f"Invalid arguments for '{tool_name}': {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error dispatching %s", tool_name)
            return OpResult(success=False, output="", error=f"Internal error: {exc}")
