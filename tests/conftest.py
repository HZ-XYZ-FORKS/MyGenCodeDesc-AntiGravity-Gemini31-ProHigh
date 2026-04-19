import pytest
import os
import subprocess
import json
import shutil
from pathlib import Path

class PhysicalVCSRepo:
    def __init__(self, tmp_path, vcs_type):
        self.tmp_path = tmp_path
        self.vcs_type = vcs_type
        self.repo_dir = self.tmp_path / f"{vcs_type}_repo"
        self.metadata_dir = self.tmp_path / "metadata"
        
        self.repo_dir.mkdir()
        self.metadata_dir.mkdir()
        
        if vcs_type == "git":
            subprocess.run(["git", "init"], cwd=self.repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir, check=True)
        elif vcs_type == "svn":
            svn_server_dir = self.tmp_path / "svn_server"
            svn_server_dir.mkdir()
            subprocess.run([shutil.which("svnadmin") or "/opt/homebrew/bin/svnadmin", "create", str(svn_server_dir)], check=True)
            # Create standard layout
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "mkdir", "-m", "Init", f"file://{svn_server_dir}/trunk"], check=True)
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "checkout", f"file://{svn_server_dir}/trunk", str(self.repo_dir)], check=True)

    def write_metadata(self, commit_id, file_name, gen_ratios, commit_time=None):
        lines = []
        for loc, ratio in gen_ratios.items():
            lines.append({"lineLocation": loc, "genRatio": ratio})
            
        data = {
            "REPOSITORY": {"revisionId": str(commit_id), "repoURL": "mock://repo"},
            "DETAIL": [{"fileName": file_name, "codeLines": lines}]
        }
        if commit_time:
            data["REPOSITORY"]["commitTime"] = commit_time
            
        with open(self.metadata_dir / f"{commit_id}.json", "w") as f:
            json.dump(data, f)
            
    def commit_file(self, filename, content, msg, timestamp_epoch=1775000000, time_iso="2026-03-31T00:00:00Z", metadata_map=None):
        file_path = self.repo_dir / filename
        with open(file_path, "w") as f:
            f.write(content)
            
        if self.vcs_type == "git":
            subprocess.run(["git", "add", filename], cwd=self.repo_dir, check=True)
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = f"{timestamp_epoch} +0000"
            env["GIT_COMMITTER_DATE"] = f"{timestamp_epoch} +0000"
            subprocess.run(["git", "commit", "-m", msg], cwd=self.repo_dir, env=env, check=True)
            res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            c_hash = res.stdout.strip()
        elif self.vcs_type == "svn":
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "add", filename], cwd=self.repo_dir, stderr=subprocess.DEVNULL)
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "commit", "-m", msg], cwd=self.repo_dir, check=True)
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "update"], cwd=self.repo_dir, check=True)
            res = subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "info", "--show-item", "revision"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            c_hash = res.stdout.strip()
            
        if metadata_map is not None:
             self.write_metadata(c_hash, filename, metadata_map, time_iso)
             
        return c_hash
        
    def rename_file(self, old_name, new_name, msg, timestamp_epoch=1775010000, time_iso="2026-04-01T00:00:00Z"):
        if self.vcs_type == "git":
            subprocess.run(["git", "mv", old_name, new_name], cwd=self.repo_dir, check=True)
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = f"{timestamp_epoch} +0000"
            env["GIT_COMMITTER_DATE"] = f"{timestamp_epoch} +0000"
            subprocess.run(["git", "commit", "-m", msg], cwd=self.repo_dir, env=env, check=True)
            res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            c_hash = res.stdout.strip()
        elif self.vcs_type == "svn":
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "mv", old_name, new_name], cwd=self.repo_dir, check=True)
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "commit", "-m", msg], cwd=self.repo_dir, check=True)
            subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "update"], cwd=self.repo_dir, check=True)
            res = subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "info", "--show-item", "revision"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            c_hash = res.stdout.strip()
        return c_hash
        
    def run_aggregator(self, start="2026-01-01T00:00:00Z", end="2026-12-31T23:59:59Z", threshold=60, alg="A"):
        script_path = os.path.abspath("aggregateGenCodeDesc.py")
        cmd = [
            "python", script_path,
            "--repoURL", "mock://repo",
            "--repoBranch", "main",
            "--startTime", start,
            "--endTime", end,
            "--threshold", str(threshold),
            "--genCodeDescDir", str(self.metadata_dir),
            "--alg", alg,
            "--log-level", "DEBUG"
        ]
        result = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True)
        assert result.returncode == 0, f"Aggregator execution failed!\\nSTDERR: {result.stderr}"
        return json.loads(result.stdout)


@pytest.fixture(params=["git", "svn"])
def vcs(tmp_path, request):
    return PhysicalVCSRepo(tmp_path, request.param)
