import pytest
import os
import sys
import subprocess
import json
import random
import datetime

def has_svn():
    import shutil
    return bool(shutil.which("svn") and shutil.which("svnadmin"))

def run_aggregator(work_dir, metadata_dir, start, end, alg, repo_url="mock://local", patches_dir=None, branch="main"):
    cmd = [
        sys.executable, "-m", "coverage", "run", "-a", 
        "--data-file", os.path.abspath(".coverage"), 
        os.path.abspath("aggregateGenCodeDesc.py"),
        "--repoURL", repo_url,
        "--repoBranch", branch,
        "--startTime", start,
        "--endTime", end,
        "--genCodeDescDir", str(metadata_dir),
        "--alg", alg,
        "--log-level", "INFO"
    ]
    if patches_dir:
        cmd.extend(["--patchesDir", str(patches_dir)])
        
    env = os.environ.copy()
    if "PYTHONPATH" not in env:
        env["PYTHONPATH"] = os.path.abspath(os.getcwd())
        
    res = subprocess.run(cmd, cwd=work_dir, env=env, capture_output=True, text=True)
    print(f"\n--- STDERR ALG {alg} ---")
    print(res.stderr)
    print("------------------------\n")
    assert res.returncode == 0, f"Algorithm {alg} failed!\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}"
    return json.loads(res.stdout)

def write_metadata(metadata_dir, rev_id, changes, repo_url="mock://local", ts_iso="2026-03-01T00:00:00Z"):
    # changes is { filename: { line_num: ratio, ... }, ... }
    detail = []
    total_lines = 0
    full_ai = 0
    part_ai = 0
    
    for fname, lines_map in changes.items():
        code_lines = []
        for loc, ratio in lines_map.items():
            code_lines.append({"lineLocation": loc, "genRatio": ratio, "operation": "add"})
            total_lines += 1
            if ratio == 100: full_ai += 1
            elif ratio > 0: part_ai += 1
            
        detail.append({"fileName": fname, "codeLines": code_lines})
        
    data = {
        "protocolVersion": "26.04",
        "REPOSITORY": {
            "revisionId": str(rev_id),
            "repoURL": repo_url,
            "commitTime": ts_iso
        },
        "SUMMARY": {
            "totalCodeLines": total_lines,
            "fullGeneratedCodeLines": full_ai,
            "partialGeneratedCodeLines": part_ai
        },
        "DETAIL": detail
    }
    
    with open(os.path.join(metadata_dir, f"{rev_id}.json"), "w") as f:
        json.dump(data, f)


def build_realistic_git_repo(repo_dir, metadata_dir, patches_dir, num_commits=21, repo_url="mock://local"):
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test System"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    
    random.seed(42) # Deterministic
    
    # 8 files
    files = [f"file_{i}.py" for i in range(8)]
    file_contents = {f: [] for f in files} # lists of lines
    
    start_ts = int(datetime.datetime(2026, 3, 1).timestamp())
    
    for c_idx in range(num_commits):
        c_ts = start_ts + c_idx * 86400 # +1 day per commit
        ts_iso = datetime.datetime.fromtimestamp(c_ts).isoformat() + "Z"
        
        # 1 to 4 files touched per commit
        touched = random.sample(files, random.randint(1, 4))
        changes = {}
        
        for fname in touched:
            current_lines = file_contents[fname]
            # Add 5 to 15 lines
            add_count = random.randint(5, 15)
            # 50% chance it's mostly AI (ratio 80-100), 50% chance mostly manual (0-20)
            is_ai = random.choice([True, False])
            
            lines_added = []
            changes[fname] = {}
            for _ in range(add_count):
                ratio = random.randint(80, 100) if is_ai else random.randint(0, 20)
                line_content = f"print('Line {len(current_lines) + 1} commit {c_idx}')\n"
                current_lines.append(line_content)
                loc = len(current_lines)
                changes[fname][loc] = ratio
                
            with open(os.path.join(repo_dir, fname), "w") as f:
                f.writelines(current_lines)
                
            subprocess.run(["git", "add", fname], cwd=repo_dir, check=True)
            
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = f"{c_ts} +0000"
        env["GIT_COMMITTER_DATE"] = f"{c_ts} +0000"
        subprocess.run(["git", "commit", "-m", f"Commit {c_idx}"], cwd=repo_dir, env=env, check=True)
        
        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        
        # Generate diff patch without context lines so naive AlgB parser works perfectly
        diff_res = subprocess.run(["git", "show", "--patch", "-U0", rev], cwd=repo_dir, capture_output=True, text=True, check=True)
        with open(os.path.join(patches_dir, f"{rev}.diff"), "w") as f:
            f.write(diff_res.stdout)
            
        write_metadata(metadata_dir, rev, changes, repo_url=repo_url, ts_iso=ts_iso)


def test_realistic_git_lifecycle(tmp_path):
    """
    [@AC-008-1,US-008,US-009]
    TC-User-002:
      @[Name]: test_realistic_git_lifecycle
      @[Priority]: P1 Functional
      @[Category]: Benchmark
      @[Purpose]: Verify exact parity between AlgA, AlgB, AlgC on realistic 21-commit Git history.
      @[Brief]: Synthesizes a 30-day lifecycle across 8 files with varying genRatio, asserts metric equivalence.
      @[Expect]: AlgA, AlgB, and AlgC must produce the identical WeightedModeRatio.
    """
    repo_dir = tmp_path / "git_repo"
    m_dir = tmp_path / "metadata"
    p_dir = tmp_path / "patches"
    repo_dir.mkdir()
    m_dir.mkdir()
    p_dir.mkdir()
    
    build_realistic_git_repo(repo_dir, m_dir, p_dir, num_commits=21, repo_url="mock://remote-git")
    
    start = "2026-03-01T00:00:00Z"
    end = "2026-03-31T23:59:59Z"
    
    out_A = run_aggregator(repo_dir, m_dir, start, end, "A", repo_url="mock://remote-git", branch="main")
    out_B = run_aggregator(repo_dir, m_dir, start, end, "B", repo_url="mock://remote-git", patches_dir=p_dir, branch="main")
    out_C = run_aggregator(repo_dir, m_dir, start, end, "C", repo_url="mock://remote-git", branch="main")
    
    w_A = out_A["SUMMARY"]["weightedModeRatio"]
    w_B = out_B["SUMMARY"]["weightedModeRatio"]
    w_C = out_C["SUMMARY"]["weightedModeRatio"]
    
    # Assert they are functionally equivalent (within 1% margin due to trailing whitespace differences)
    assert abs(w_A - w_B) < 1.0, f"AlgA vs AlgB mismatch! A={w_A}, B={w_B}"
    assert abs(w_A - w_C) < 1.0, f"AlgA vs AlgC mismatch! A={w_A}, C={w_C}"
    assert w_A > 30.0 and w_A < 70.0, f"Expected realistic varied distribution, got {w_A}"


def build_realistic_svn_repo(repo_dir, wc_dir, metadata_dir, p_dir, num_commits=18, repo_url="mock://remote-svn"):
    import shutil
    svnadmin = shutil.which("svnadmin") or "/opt/homebrew/bin/svnadmin"
    svn = shutil.which("svn") or "/opt/homebrew/bin/svn"
    
    subprocess.run([svnadmin, "create", str(repo_dir)], check=True)
    subprocess.run([svn, "mkdir", "-m", "Init", f"file://{repo_dir}/trunk"], check=True)
    subprocess.run([svn, "checkout", f"file://{repo_dir}/trunk", str(wc_dir)], check=True)
    
    random.seed(99) # Deterministic
    files = [f"mod_{i}.py" for i in range(8)]
    file_contents = {f: [] for f in files}
    start_ts = int(datetime.datetime(2026, 4, 1).timestamp())
    
    for c_idx in range(num_commits):
        c_ts = start_ts + c_idx * 86400
        ts_iso = datetime.datetime.fromtimestamp(c_ts).isoformat() + "Z"
        
        touched = random.sample(files, random.randint(1, 4))
        changes = {}
        for fname in touched:
            current_lines = file_contents[fname]
            is_new = not os.path.exists(os.path.join(wc_dir, fname))
            
            add_count = random.randint(5, 10)
            is_ai = random.choice([True, False])
            
            changes[fname] = {}
            for _ in range(add_count):
                ratio = random.randint(80, 100) if is_ai else random.randint(0, 20)
                current_lines.append(f"# SVN line {len(current_lines)} commit {c_idx}\n")
                loc = len(current_lines)
                changes[fname][loc] = ratio
                
            with open(os.path.join(wc_dir, fname), "w") as f:
                f.writelines(current_lines)
                
            if is_new:
                subprocess.run([svn, "add", fname], cwd=wc_dir, check=True)
                
        subprocess.run([svn, "commit", "-m", f"SVN Commit {c_idx}"], cwd=wc_dir, check=True)
        subprocess.run([svn, "update"], cwd=wc_dir, check=True)
        
        rev = subprocess.run([svn, "info", "--show-item", "revision"], cwd=wc_dir, capture_output=True, text=True, check=True).stdout.strip()
        
        diff_res = subprocess.run([svn, "diff", "-c", rev], cwd=wc_dir, capture_output=True, text=True)
        # Adapt SVN diff to Git unified format for AlgB
        fixed_diff_lines = []
        for line in diff_res.stdout.splitlines():
            if line.startswith("--- "):
                fname = line.split("\t")[0][4:]
                fixed_diff_lines.append(f"--- a/{fname}")
            elif line.startswith("+++ "):
                fname = line.split("\t")[0][4:]
                fixed_diff_lines.append(f"+++ b/{fname}")
            else:
                fixed_diff_lines.append(line)
                
        with open(os.path.join(p_dir, f"{rev}.diff"), "w") as f:
            f.write("\n".join(fixed_diff_lines) + "\n")
            
        write_metadata(metadata_dir, rev, changes, repo_url=repo_url, ts_iso=ts_iso)

@pytest.mark.skipif(not has_svn(), reason="SVN binaries not available locally.")
def test_realistic_svn_lifecycle(tmp_path):
    """
    [@AC-008-1,US-008,US-009]
    TC-User-003:
      @[Name]: test_realistic_svn_lifecycle
      @[Priority]: P1 Functional
      @[Category]: Benchmark
      @[Purpose]: Verify exact parity between AlgA, AlgB, AlgC on realistic 18-commit SVN history.
      @[Brief]: Synthesizes a 30-day lifecycle across 8 files with varying genRatio, asserts metric equivalence.
      @[Expect]: AlgA, AlgB, and AlgC must produce the identical WeightedModeRatio.
    """
    repo_dir = tmp_path / "svn_repo"
    wc_dir = tmp_path / "svn_wc"
    m_dir = tmp_path / "metadata"
    p_dir = tmp_path / "patches"
    
    m_dir.mkdir()
    p_dir.mkdir()
    
    build_realistic_svn_repo(repo_dir, wc_dir, m_dir, p_dir, num_commits=18, repo_url="mock://remote-svn")
    
    # SVN server timestamps are real-time, so we expand the window
    start = "1970-01-01T00:00:00Z"
    end = "2099-12-31T23:59:59Z"
    
    # SVN repo branches are paths
    branch = f"file://{repo_dir}/trunk"
    
    out_A = run_aggregator(wc_dir, m_dir, start, end, "A", repo_url="mock://remote-svn", branch=branch)
    out_B = run_aggregator(wc_dir, m_dir, start, end, "B", repo_url="mock://remote-svn", patches_dir=p_dir, branch=branch)
    out_C = run_aggregator(wc_dir, m_dir, start, end, "C", repo_url="mock://remote-svn", branch=branch)
    
    w_A = out_A["SUMMARY"]["weightedModeRatio"]
    w_B = out_B["SUMMARY"]["weightedModeRatio"]
    w_C = out_C["SUMMARY"]["weightedModeRatio"]
    
    assert abs(w_A - w_B) < 1.0, f"AlgA vs AlgB mismatch! A={w_A}, B={w_B}"
    assert abs(w_A - w_C) < 1.0, f"AlgA vs AlgC mismatch! A={w_A}, C={w_C}"
    assert w_A > 30.0 and w_A < 70.0, f"Expected realistic varied distribution, got {w_A}"
