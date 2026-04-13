"""
Git and filesystem operations for the Eidolon agent.

Every operation goes through the SecurityGate before execution.
"""
from __future__ import annotations

import fnmatch
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .auth import AuthResult, SecurityGate

logger = logging.getLogger("eidolon.operations")


@dataclass
class OpResult:
    """Result of an Eidolon operation."""
    success: bool
    output: str
    error: str | None = None


def _run_git(args: list[str], cwd: Path, timeout: int = 60) -> OpResult:
    """Run a git command safely."""
    cmd = ["git"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return OpResult(success=True, output=proc.stdout.strip())
        return OpResult(success=False, output=proc.stdout.strip(), error=proc.stderr.strip())
    except subprocess.TimeoutExpired:
        return OpResult(success=False, output="", error=f"Command timed out after {timeout}s")
    except Exception as exc:
        return OpResult(success=False, output="", error=str(exc))


class GitOperations:
    """Secured git operations, gated through Eidolon's SecurityGate."""

    def __init__(self, repo_path: Path, gate: SecurityGate):
        self.repo_path = repo_path.resolve()
        self.gate = gate

    def _check(self, operation: str, path: str | Path | None = None, token: str | None = None) -> AuthResult:
        return self.gate.gate(operation, path, token)

    def status(self, token: str | None = None) -> OpResult:
        auth = self._check("status", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        return _run_git(["status", "--porcelain", "-b"], self.repo_path)

    def pull(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        auth = self._check("pull", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["pull", remote]
        if branch:
            args.append(branch)
        return _run_git(args, self.repo_path)

    def fetch(self, remote: str = "origin", branch: str | None = None, token: str | None = None) -> OpResult:
        auth = self._check("fetch", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["fetch", remote]
        if branch:
            args.append(branch)
        return _run_git(args, self.repo_path)

    def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        set_upstream: bool = True,
        token: str | None = None,
    ) -> OpResult:
        """Push (publish) to remote. Uses -u by default to set tracking."""
        auth = self._check("push", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.append(remote)
        if branch:
            args.append(branch)
        return _run_git(args, self.repo_path)

    def publish(
        self,
        remote: str = "origin",
        branch: str | None = None,
        token: str | None = None,
    ) -> OpResult:
        """Alias for push with upstream tracking -- the 'publish' action."""
        return self.push(remote=remote, branch=branch, set_upstream=True, token=token)

    def commit(self, message: str, add_all: bool = False, files: list[str] | None = None, token: str | None = None) -> OpResult:
        auth = self._check("commit", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)

        # Stage files
        if files:
            for f in files:
                file_auth = self.gate.gate("commit", self.repo_path / f, token)
                if not file_auth.allowed:
                    return OpResult(success=False, output="", error=f"Cannot stage '{f}': {file_auth.reason}")
            stage_result = _run_git(["add", "--"] + files, self.repo_path)
        elif add_all:
            stage_result = _run_git(["add", "-A"], self.repo_path)
        else:
            stage_result = OpResult(success=True, output="No staging requested")

        if not stage_result.success:
            return stage_result

        return _run_git(["commit", "-m", message], self.repo_path)

    def diff(self, staged: bool = False, path: str | None = None, token: str | None = None) -> OpResult:
        auth = self._check("diff", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["diff"]
        if staged:
            args.append("--cached")
        if path:
            path_auth = self.gate.gate("diff", self.repo_path / path, token)
            if not path_auth.allowed:
                return OpResult(success=False, output="", error=path_auth.reason)
            args.extend(["--", path])
        return _run_git(args, self.repo_path)

    def log(self, max_count: int = 20, oneline: bool = True, token: str | None = None) -> OpResult:
        auth = self._check("log", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["log", f"--max-count={max_count}"]
        if oneline:
            args.append("--oneline")
        return _run_git(args, self.repo_path)

    def branch(
        self,
        name: str | None = None,
        create: bool = False,
        delete: bool = False,
        list_all: bool = False,
        token: str | None = None,
    ) -> OpResult:
        auth = self._check("branch", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["branch"]
        if list_all:
            args.append("-a")
        elif create and name:
            args.append(name)
        elif delete and name:
            args.extend(["-d", name])
        return _run_git(args, self.repo_path)

    def checkout(self, target: str, create: bool = False, token: str | None = None) -> OpResult:
        auth = self._check("checkout", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(target)
        return _run_git(args, self.repo_path)

    def merge(self, branch: str, no_ff: bool = True, token: str | None = None) -> OpResult:
        auth = self._check("merge", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        args = ["merge"]
        if no_ff:
            args.append("--no-ff")
        args.append(branch)
        return _run_git(args, self.repo_path)


class FileOperations:
    """Secured filesystem operations, gated through Eidolon's SecurityGate."""

    def __init__(self, repo_path: Path, gate: SecurityGate):
        self.repo_path = repo_path.resolve()
        self.gate = gate

    def read_file(self, rel_path: str, token: str | None = None) -> OpResult:
        auth = self.gate.gate("file_read", self.repo_path / rel_path, token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        target = self.repo_path / rel_path
        if not target.exists():
            return OpResult(success=False, output="", error=f"File not found: {rel_path}")
        try:
            content = target.read_text(encoding="utf-8")
            return OpResult(success=True, output=content)
        except Exception as exc:
            return OpResult(success=False, output="", error=str(exc))

    def write_file(self, rel_path: str, content: str, token: str | None = None) -> OpResult:
        auth = self.gate.gate("file_write", self.repo_path / rel_path, token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        target = self.repo_path / rel_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return OpResult(success=True, output=f"Wrote {len(content)} bytes to {rel_path}")
        except Exception as exc:
            return OpResult(success=False, output="", error=str(exc))

    def list_files(self, rel_path: str = ".", pattern: str = "*", token: str | None = None) -> OpResult:
        auth = self.gate.gate("file_search", self.repo_path / rel_path, token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        target = self.repo_path / rel_path
        if not target.is_dir():
            return OpResult(success=False, output="", error=f"Not a directory: {rel_path}")
        matches = sorted(str(p.relative_to(self.repo_path)) for p in target.rglob(pattern) if p.is_file())
        # Filter out denied patterns
        filtered = []
        for m in matches:
            check = self.gate.check_file_pattern(m)
            if check.allowed:
                filtered.append(m)
        return OpResult(success=True, output="\n".join(filtered))

    def search_content(self, pattern: str, glob: str = "**/*", token: str | None = None) -> OpResult:
        auth = self.gate.gate("file_search", token=token)
        if not auth.allowed:
            return OpResult(success=False, output="", error=auth.reason)
        results: list[str] = []
        for fpath in self.repo_path.rglob(glob):
            if not fpath.is_file():
                continue
            if not self.gate.check_file_pattern(str(fpath.relative_to(self.repo_path))).allowed:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern in line:
                        rel = fpath.relative_to(self.repo_path)
                        results.append(f"{rel}:{i}: {line.strip()}")
            except Exception:
                continue
        return OpResult(success=True, output="\n".join(results[:200]))
