"""
Vecto Proxy - The secure proxy layer between MCP clients and the Eidolon agent.

Vecto intercepts all requests, applies rate limiting, audit logging,
and origin validation before forwarding to the router.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..eidolon.agent import EidolonAgent
from ..eidolon.operations import OpResult
from .router import VectoRouter

logger = logging.getLogger("vecto.proxy")


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: float
    tool_name: str
    success: bool
    caller: str
    detail: str


class VectoProxy:
    """
    Secure proxy layer that sits between MCP transport and Eidolon.

    Responsibilities:
    - Origin/caller validation
    - Rate limiting per caller
    - Audit logging of all operations
    - Request forwarding via VectoRouter
    """

    def __init__(
        self,
        agent: EidolonAgent,
        allowed_origins: list[str] | None = None,
        rate_limit_per_minute: int = 60,
    ):
        self.router = VectoRouter(agent)
        self._allowed_origins = set(allowed_origins or ["localhost", "127.0.0.1"])
        self._rate_limit = rate_limit_per_minute
        self._call_timestamps: dict[str, list[float]] = defaultdict(list)
        self._audit_log: list[AuditEntry] = []

    def _check_origin(self, origin: str) -> bool:
        """Validate that the caller's origin is allowed."""
        if not self._allowed_origins:
            return True
        return origin in self._allowed_origins

    def _check_rate_limit(self, caller: str) -> bool:
        """Enforce rate limiting per caller."""
        now = time.monotonic()
        window_start = now - 60.0
        # Prune old timestamps
        self._call_timestamps[caller] = [
            t for t in self._call_timestamps[caller] if t > window_start
        ]
        if len(self._call_timestamps[caller]) >= self._rate_limit:
            return False
        self._call_timestamps[caller].append(now)
        return True

    def _audit(self, tool_name: str, success: bool, caller: str, detail: str) -> None:
        """Record an audit entry."""
        entry = AuditEntry(
            timestamp=time.time(),
            tool_name=tool_name,
            success=success,
            caller=caller,
            detail=detail,
        )
        self._audit_log.append(entry)
        # Keep audit log bounded
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
        logger.info("AUDIT: %s %s by %s: %s", tool_name, "OK" if success else "FAIL", caller, detail)

    def get_audit_log(self, last_n: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit entries."""
        entries = self._audit_log[-last_n:]
        return [
            {
                "timestamp": e.timestamp,
                "tool": e.tool_name,
                "success": e.success,
                "caller": e.caller,
                "detail": e.detail,
            }
            for e in entries
        ]

    def handle_request(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        caller: str = "local",
        origin: str = "localhost",
    ) -> OpResult:
        """
        Main entry point for all MCP tool calls.

        Validates origin, checks rate limits, dispatches through the router,
        and records the audit trail.
        """
        # Origin check
        if not self._check_origin(origin):
            detail = f"Origin '{origin}' not in allowed list"
            self._audit(tool_name, False, caller, detail)
            return OpResult(success=False, output="", error=detail)

        # Rate limit
        if not self._check_rate_limit(caller):
            detail = f"Rate limit exceeded ({self._rate_limit}/min)"
            self._audit(tool_name, False, caller, detail)
            return OpResult(success=False, output="", error=detail)

        # Dispatch through router -> Eidolon agent
        result = self.router.dispatch(tool_name, dict(arguments))

        self._audit(
            tool_name,
            result.success,
            caller,
            result.error or "success",
        )

        return result

    def list_tools(self) -> list[dict[str, str]]:
        """List all available tools through the proxy."""
        return self.router.list_routes()
