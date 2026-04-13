"""
Eidolon - The core secure agent that orchestrates all repo operations.

Eidolon wraps git and file operations behind a SecurityGate, providing
a unified interface that the MCP server and Vecto proxy call into.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .auth import SecurityGate
from .operations import FileOperations, GitOperations, OpResult

logger = logging.getLogger("eidolon.agent")


class EidolonAgent:
    """
    Secure agent for repository management.

    All operations are gated through the SecurityGate. The agent provides
    a high-level API that the MCP server tools and Vecto proxy dispatch to.
    """

    def __init__(
        self,
        repo_path: Path,
        allowed_paths: list[str] | None = None,
        allowed_operations: list[str] | None = None,
        denied_patterns: list[str] | None = None,
        auth_token: str | None = None,
        max_file_size_bytes: int = 10 * 1024 * 1024,
    ):
        self.repo_path = repo_path.resolve()

        if allowed_paths is None:
            allowed_paths = [str(self.repo_path)]
        if allowed_operations is None:
            allowed_operations = [
                "status", "pull", "push", "commit", "branch",
                "diff", "log", "fetch", "checkout", "merge",
                "file_read", "file_write", "file_search",
            ]
        if denied_patterns is None:
            denied_patterns = [
                "*.env", "*.pem", "*.key", "*.secret",
                "*credentials*", "*password*", "*.p12", "*.pfx",
            ]

        self.gate = SecurityGate(
            allowed_paths=allowed_paths,
            allowed_operations=allowed_operations,
            denied_patterns=denied_patterns,
            auth_token=auth_token,
            max_file_size_bytes=max_file_size_bytes,
        )

        self.git = GitOperations(self.repo_path, self.gate)
        self.files = FileOperations(self.repo_path, self.gate)

        logger.info("Eidolon agent initialized for repo: %s", self.repo_path)

    # -- High-level API --

    def status(self, token: str | None = None) -> OpResult:
        """Get repository status."""
        return self.git.status(token=token)

    def pull(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        """Pull from remote."""
        return self.git.pull(remote=remote, branch=branch, token=token)

    def fetch(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        """Fetch from remote."""
        return self.git.fetch(remote=remote, branch=branch, token=token)

    def publish(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        """Publish (push with upstream tracking) to remote."""
        return self.git.publish(remote=remote, branch=branch, token=token)

    def push(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        """Push to remote."""
        return self.git.push(remote=remote, branch=branch, set_upstream=True, token=token)

    def commit(
        self,
        message: str,
        add_all: bool = False,
        files: list[str] | None = None,
        token: str | None = None,
    ) -> OpResult:
        """Stage and commit changes."""
        return self.git.commit(message=message, add_all=add_all, files=files, token=token)

    def diff(self, staged: bool = False, path: str | None = None, token: str | None = None) -> OpResult:
        """Show diff."""
        return self.git.diff(staged=staged, path=path, token=token)

    def log(self, max_count: int = 20, token: str | None = None) -> OpResult:
        """Show commit log."""
        return self.git.log(max_count=max_count, token=token)

    def branch(
        self,
        name: str | None = None,
        create: bool = False,
        delete: bool = False,
        list_all: bool = False,
        token: str | None = None,
    ) -> OpResult:
        """Branch operations."""
        return self.git.branch(name=name, create=create, delete=delete, list_all=list_all, token=token)

    def checkout(self, target: str, create: bool = False, token: str | None = None) -> OpResult:
        """Checkout a branch or ref."""
        return self.git.checkout(target=target, create=create, token=token)

    def merge(self, branch: str, token: str | None = None) -> OpResult:
        """Merge a branch into current."""
        return self.git.merge(branch=branch, token=token)

    def read_file(self, path: str, token: str | None = None) -> OpResult:
        """Read a file from the repo."""
        return self.files.read_file(path, token=token)

    def write_file(self, path: str, content: str, token: str | None = None) -> OpResult:
        """Write a file to the repo."""
        return self.files.write_file(path, content, token=token)

    def list_files(self, path: str = ".", pattern: str = "*", token: str | None = None) -> OpResult:
        """List files in the repo."""
        return self.files.list_files(path, pattern=pattern, token=token)

    def search(self, pattern: str, glob: str = "**/*", token: str | None = None) -> OpResult:
        """Search file contents."""
        return self.files.search_content(pattern, glob=glob, token=token)
