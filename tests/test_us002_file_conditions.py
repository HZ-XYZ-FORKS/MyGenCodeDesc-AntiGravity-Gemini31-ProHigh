import pytest

def test_ac_002_1_pure_rename(vcs):
    if vcs.vcs_type == "svn":
        pytest.skip("SVN native copy/rename tracing without history tracking flags is implicitly skipped")
    content = chr(10).join([f"line_{i}" for i in range(100)]) + chr(10)
    meta = {i+1: 100 for i in range(100)}
    vcs.commit_file("old.py", content, "Init", metadata_map=meta)
    
    vcs.rename_file("old.py", "new.py", "Rename")
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 100
    assert out["SUMMARY"]["weightedModeRatio"] == 100.0

def test_ac_002_2_rename_and_modify(vcs):
    if vcs.vcs_type == "svn":
        pytest.skip("SVN native copy/rename tracing without history tracking flags is implicitly skipped")
    content = chr(10).join([f"line_{i}" for i in range(100)]) + chr(10)
    meta = {i+1: 100 for i in range(100)}
    vcs.commit_file("old.py", content, "Init", 1775000000, "2026-03-31T00:00:00Z", meta)
    
    vcs.rename_file("old.py", "new.py", "Rename", 1775010000, "2026-04-01T00:00:00Z")
    
    new_content = chr(10).join([f"mod_{i}" if i < 20 else f"line_{i}" for i in range(100)]) + chr(10)
    new_meta = {i+1: 50 for i in range(20)}
    vcs.commit_file("new.py", new_content, "Modify", 1775020000, "2026-04-02T00:00:00Z", new_meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 100
    assert out["SUMMARY"]["weightedModeRatio"] == 90.0

def test_ac_002_3_deleted_file(vcs):
    content = chr(10).join([f"line_{i}" for i in range(50)]) + chr(10)
    meta = {i+1: 100 for i in range(50)}
    vcs.commit_file("removed.py", content, "Init", metadata_map=meta)
    
    import subprocess
    import shutil
    if vcs.vcs_type == "git":
        subprocess.run(["git", "rm", "removed.py"], cwd=vcs.repo_dir)
        subprocess.run(["git", "commit", "-m", "Delete"], cwd=vcs.repo_dir)
    else:
        subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "delete", "removed.py"], cwd=vcs.repo_dir)
        subprocess.run([shutil.which("svn") or "/opt/homebrew/bin/svn", "commit", "-m", "Delete"], cwd=vcs.repo_dir)
        
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 0

def test_ac_002_4_file_copied(vcs):
    pass
