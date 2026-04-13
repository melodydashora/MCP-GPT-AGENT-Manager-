"""
Security gate for Eidolon agent operations.

Enforces path restrictions, operation allowlists, and file-pattern denylists
before any git or filesystem operation is executed.
"""
from __future__ import annotations

import fnmatch
import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("eidolon.auth")


@dataclass
class AuthResult:
    """Result of a security check."""
    allowed: bool
    reason: str


class SecurityGate:
    """
    Guards all operations that Eidolon performs.

    - Validates that target paths are within the allowed repo boundary.
    - Checks operations against an allowlist.
    - Rejects file access matching denied patterns (secrets, keys, etc.).
    - Optionally validates bearer tokens for remote callers.
    """

    def __init__(
        self,
        allowed_paths: list[str],
        allowed_operations: list[str],
        denied_patterns: list[str],
        auth_token: str | None = None,
        max_file_size_bytes: int = 10 * 1024 * 1024,
    ):
        self._allowed_paths = [Path(p).resolve() for p in allowed_paths]
        self._allowed_operations = set(allowed_operations)
        self._denied_patterns = denied_patterns
        self._max_file_size = max_file_size_bytes
        # Hash the token so we never store it in plaintext in memory
        if auth_token:
            self._token_hash = hashlib.sha256(auth_token.encode()).hexdigest()
        else:
            self._token_hash = None

    def verify_token(self, token: str | None) -> AuthResult:
        """Verify a bearer token if token auth is enabled."""
        if self._token_hash is None:
            return AuthResult(allowed=True, reason="Token auth not configured")
        if token is None:
            return AuthResult(allowed=False, reason="Missing authentication token")
        candidate_hash = hashlib.sha256(token.encode()).hexdigest()
        if hmac.compare_digest(candidate_hash, self._token_hash):
            return AuthResult(allowed=True, reason="Token verified")
        return AuthResult(allowed=False, reason="Invalid authentication token")

    def check_operation(self, operation: str) -> AuthResult:
        """Check if an operation is in the allowlist."""
        if operation in self._allowed_operations:
            return AuthResult(allowed=True, reason=f"Operation '{operation}' is permitted")
        return AuthResult(
            allowed=False,
            reason=f"Operation '{operation}' is not in the allowlist: {sorted(self._allowed_operations)}",
        )

    def check_path(self, target_path: str | Path) -> AuthResult:
        """Ensure a path is within the allowed repository boundary."""
        resolved = Path(target_path).resolve()
        for allowed in self._allowed_paths:
            if resolved == allowed or allowed in resolved.parents:
                return AuthResult(allowed=True, reason=f"Path is within allowed boundary: {allowed}")
        return AuthResult(
            allowed=False,
            reason=f"Path '{resolved}' is outside all allowed boundaries",
        )

    def check_file_pattern(self, filename: str) -> AuthResult:
        """Reject files matching denied patterns (secrets, keys, etc.)."""
        basename = Path(filename).name
        for pattern in self._denied_patterns:
            if fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(filename, pattern):
                return AuthResult(
                    allowed=False,
                    reason=f"File '{filename}' matches denied pattern '{pattern}'",
                )
        return AuthResult(allowed=True, reason="File does not match any denied patterns")

    def check_file_size(self, file_path: str | Path) -> AuthResult:
        """Reject files that exceed the maximum allowed size."""
        path = Path(file_path)
        if path.exists():
            size = path.stat().st_size
            if size > self._max_file_size:
                return AuthResult(
                    allowed=False,
                    reason=f"File size {size} bytes exceeds limit of {self._max_file_size} bytes",
                )
        return AuthResult(allowed=True, reason="File size within limits")

    def gate(
        self,
        operation: str,
        target_path: str | Path | None = None,
        token: str | None = None,
    ) -> AuthResult:
        """
        Run the full security gate for an operation.

        Returns the first failing AuthResult, or a passing result if all checks pass.
        """
        checks = [
            self.verify_token(token),
            self.check_operation(operation),
        ]
        if target_path is not None:
            checks.append(self.check_path(target_path))
            checks.append(self.check_file_pattern(str(target_path)))
            if Path(target_path).exists():
                checks.append(self.check_file_size(target_path))

        for result in checks:
            if not result.allowed:
                logger.warning("Security gate DENIED: %s", result.reason)
                return result

        logger.info("Security gate ALLOWED: operation=%s path=%s", operation, target_path)
        return AuthResult(allowed=True, reason="All security checks passed")
