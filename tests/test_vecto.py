"""Tests for the Vecto proxy layer."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from src.eidolon.agent import EidolonAgent
from src.vecto.proxy import VectoProxy


class TestVectoProxy:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.tmpdir, capture_output=True)

        agent = EidolonAgent(repo_path=Path(self.tmpdir))
        self.proxy = VectoProxy(
            agent=agent,
            allowed_origins=["localhost", "127.0.0.1"],
        )

    def test_valid_request(self):
        result = self.proxy.handle_request("repo_status", {}, origin="localhost")
        assert result.success

    def test_blocked_origin(self):
        result = self.proxy.handle_request("repo_status", {}, origin="evil.com")
        assert not result.success
        assert "not in allowed list" in result.error

    def test_unknown_tool(self):
        result = self.proxy.handle_request("nonexistent_tool", {}, origin="localhost")
        assert not result.success

    def test_audit_log_recorded(self):
        self.proxy.handle_request("repo_status", {}, origin="localhost")
        log = self.proxy.get_audit_log(last_n=10)
        assert len(log) == 1
        assert log[0]["tool"] == "repo_status"
        assert log[0]["success"] is True

    def test_rate_limiting(self):
        proxy = VectoProxy(
            agent=EidolonAgent(repo_path=Path(self.tmpdir)),
            rate_limit_per_minute=3,
        )
        for _ in range(3):
            result = proxy.handle_request("repo_status", {}, caller="test", origin="localhost")
            assert result.success
        # 4th call should be rate-limited
        result = proxy.handle_request("repo_status", {}, caller="test", origin="localhost")
        assert not result.success
        assert "Rate limit" in result.error

    def test_file_write_through_proxy(self):
        result = self.proxy.handle_request(
            "file_write",
            {"path": "proxy_test.txt", "content": "via vecto"},
            origin="localhost",
        )
        assert result.success

        result = self.proxy.handle_request(
            "file_read",
            {"path": "proxy_test.txt"},
            origin="localhost",
        )
        assert result.success
        assert result.output == "via vecto"

    def test_list_tools(self):
        tools = self.proxy.list_tools()
        tool_names = [t["tool"] for t in tools]
        assert "repo_status" in tool_names
        assert "repo_publish" in tool_names
        assert "file_read" in tool_names
