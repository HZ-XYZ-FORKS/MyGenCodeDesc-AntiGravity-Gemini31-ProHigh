import os
import subprocess
import pytest
import json

def test_user_guided_walkthrough(tmp_path):
    """
    [@AC-001-1,US-001]
    TC-User-001:
      @[Name]: test_user_guided_walkthrough
      @[Priority]: P4 Addons
      @[Category]: Demo/Example
      @[Purpose]: Demonstrate the README_UserGuide flow for a maintainer.
      @[Brief]: Set up a demo repo and run the full aggregateGenCodeDesc CLI command, asserting readable output.
      @[Expect]: The user can identify metrics in stdout without crashes.
    """
    repo_dir = tmp_path / "demo_repo"
    m_dir = tmp_path / "metadata"
    repo_dir.mkdir()
    m_dir.mkdir()
    
    # Setup mock repository with mock commits
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Demo User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=repo_dir, check=True)
    
    with open(repo_dir / "main.py", "w") as f:
        f.write("print('Hello World')\n")
        
    subprocess.run(["git", "add", "main.py"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)
    
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
    commit_id = res.stdout.strip()
    
    # Setup mock genCodeDesc
    with open(m_dir / f"{commit_id}.json", "w") as f:
        json.dump({
            "protocolVersion": "26.04",
            "REPOSITORY": {"revisionId": commit_id, "repoURL": "mock://demo", "commitTime": "2026-05-01T10:00:00Z"},
            "SUMMARY": {"lineCount": 1},
            "DETAIL": [{"fileName": "main.py", "codeLines": [{"lineLocation": 1, "operation": "add", "genRatio": 100}]}]
        }, f)
        
    import sys
    script_path = os.path.abspath("aggregateGenCodeDesc.py")
    
    # Run the user guide command
    result = subprocess.run([
        sys.executable, "-m", "coverage", "run", "-a", "--data-file", "/Users/enigmawu/HZ-XYZ-FORKS/MyGenCodeDesc-AntiGravity-Gemini31-ProHigh/.coverage", script_path,
        "--repoURL", "mock://demo",
        "--repoBranch", "main",
        "--startTime", "2026-01-01T00:00:00Z",
        "--endTime", "2026-12-31T23:59:59Z",
        "--genCodeDescDir", str(m_dir),
        "--alg", "A"
    ], cwd=repo_dir, capture_output=True, text=True)
    
    # Output assertions reflecting human-readability
    assert result.returncode == 0
    assert "SUMMARY aggregate totalLines=1 weighted=100.0% fullyAI=100.0% mostlyAI=100.0%" in result.stderr
    
    # Output artifact generation parsing
    output_json = json.loads(result.stdout)
    assert output_json["SUMMARY"]["weightedModeRatio"] == 100.0
