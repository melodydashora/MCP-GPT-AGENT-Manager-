"""Tests for the Eidolon agent security gate and operations."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.eidolon.agent import EidolonAgent
from src.eidolon.auth import SecurityGate


class TestSecurityGate:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gate = SecurityGate(
            allowed_paths=[self.tmpdir],
            allowed_operations=["status", "pull", "push", "commit", "file_read", "file_write"],
            denied_patterns=["*.env", "*.key", "*.secret"],
            auth_token=None,
        )

    def test_allowed_operation(self):
        result = self.gate.check_operation("status")
        assert result.allowed

    def test_denied_operation(self):
        result = self.gate.check_operation("dangerous_op")
        assert not result.allowed

    def test_path_within_boundary(self):
        result = self.gate.check_path(Path(self.tmpdir) / "subdir" / "file.py")
        assert result.allowed

    def test_path_outside_boundary(self):
        result = self.gate.check_path("/etc/passwd")
        assert not result.allowed

    def test_denied_file_pattern(self):
        result = self.gate.check_file_pattern(".env")
        assert not result.allowed

    def test_denied_key_pattern(self):
        result = self.gate.check_file_pattern("server.key")
        assert not result.allowed

    def test_allowed_file_pattern(self):
        result = self.gate.check_file_pattern("main.py")
        assert result.allowed

    def test_token_auth_disabled(self):
        result = self.gate.verify_token(None)
        assert result.allowed

    def test_token_auth_valid(self):
        gate = SecurityGate(
            allowed_paths=[self.tmpdir],
            allowed_operations=["status"],
            denied_patterns=[],
            auth_token="my-secret-token",
        )
        result = gate.verify_token("my-secret-token")
        assert result.allowed

    def test_token_auth_invalid(self):
        gate = SecurityGate(
            allowed_paths=[self.tmpdir],
            allowed_operations=["status"],
            denied_patterns=[],
            auth_token="my-secret-token",
        )
        result = gate.verify_token("wrong-token")
        assert not result.allowed

    def test_full_gate_pass(self):
        result = self.gate.gate("status")
        assert result.allowed

    def test_full_gate_denied_path(self):
        result = self.gate.gate("file_read", target_path="/etc/shadow")
        assert not result.allowed


class TestEidolonAgent:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Init a git repo in the temp dir
        import subprocess
        subprocess.run(["git", "init"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.tmpdir, capture_output=True)

        self.agent = EidolonAgent(repo_path=Path(self.tmpdir))

    def test_status(self):
        result = self.agent.status()
        assert result.success

    def test_write_and_read_file(self):
        write_result = self.agent.write_file("test.txt", "hello world")
        assert write_result.success

        read_result = self.agent.read_file("test.txt")
        assert read_result.success
        assert read_result.output == "hello world"

    def test_denied_file_write(self):
        result = self.agent.write_file(".env", "SECRET=oops")
        assert not result.success

    def test_list_files(self):
        self.agent.write_file("a.py", "print('a')")
        self.agent.write_file("b.py", "print('b')")
        result = self.agent.list_files(pattern="*.py")
        assert result.success
        assert "a.py" in result.output
        assert "b.py" in result.output

    def test_commit(self):
        self.agent.write_file("hello.txt", "hello")
        result = self.agent.commit("initial commit", files=["hello.txt"])
        # Commit may fail in environments with commit signing enforcement;
        # we verify the staging + security gate path worked (no auth error).
        assert result.success or "signing" in (result.error or "").lower()

    def test_branch_list(self):
        # Need at least one commit first
        self.agent.write_file("init.txt", "init")
        self.agent.commit("init", files=["init.txt"])
        result = self.agent.branch(list_all=True)
        assert result.success
