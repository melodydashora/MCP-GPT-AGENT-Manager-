"""
Configuration settings for the MCP Agent Manager.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VectoConfig:
    """Vecto proxy configuration."""
    host: str = "127.0.0.1"
    port: int = int(os.environ.get("VECTO_PORT", "8781"))
    max_retries: int = 3
    timeout_seconds: int = 30
    allowed_origins: list[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])


@dataclass(frozen=True)
class EidolonConfig:
    """Eidolon agent security configuration."""
    # Paths the agent is allowed to operate on
    allowed_paths: list[str] = field(default_factory=lambda: [
        os.environ.get("EIDOLON_REPO_PATH", os.getcwd()),
    ])
    # Git operations that are permitted
    allowed_operations: list[str] = field(default_factory=lambda: [
        "status", "pull", "push", "commit", "branch",
        "diff", "log", "fetch", "checkout", "merge",
        "file_read", "file_write", "file_search",
    ])
    # Maximum file size for read/write operations (10MB default)
    max_file_size_bytes: int = 10 * 1024 * 1024
    # Patterns to never touch (secrets, credentials)
    denied_patterns: list[str] = field(default_factory=lambda: [
        "*.env", "*.pem", "*.key", "*.secret",
        "*credentials*", "*password*", "*.p12", "*.pfx",
    ])
    # Token for authentication (set via env var)
    auth_token: str | None = field(default_factory=lambda: os.environ.get("EIDOLON_AUTH_TOKEN"))


@dataclass(frozen=True)
class ServerConfig:
    """Top-level server configuration."""
    name: str = "mcp-gpt-agent-manager"
    version: str = "0.1.0"
    repo_path: Path = field(default_factory=lambda: Path(os.environ.get("EIDOLON_REPO_PATH", os.getcwd())))
    vecto: VectoConfig = field(default_factory=VectoConfig)
    eidolon: EidolonConfig = field(default_factory=EidolonConfig)


def load_config() -> ServerConfig:
    """Load configuration from environment."""
    return ServerConfig()
