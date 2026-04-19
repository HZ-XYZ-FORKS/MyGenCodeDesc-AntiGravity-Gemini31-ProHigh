import pytest
import subprocess
import json
import os
import shutil

SVN_BIN = shutil.which("svn") or "/opt/homebrew/bin/svn"
SVNADMIN_BIN = shutil.which("svnadmin") or "/opt/homebrew/bin/svnadmin"

def has_svn():
    return os.path.exists(SVN_BIN) and os.path.exists(SVNADMIN_BIN)

pytestmark = pytest.mark.skipif(not has_svn(), reason="SVN binaries not available locally.")

def setup_svn_repo(tmp_path):
    # Setup SVN db
    repo_dir = tmp_path / "svn_repo"
    subprocess.run([SVNADMIN_BIN, "create", str(repo_dir)], check=True)
    
    # Checkout working copy
    wc_dir = tmp_path / "svn_wc"
    subprocess.run([SVN_BIN, "checkout", f"file://{repo_dir}", str(wc_dir)], check=True)
    return wc_dir

def commit_file_svn(wc_dir, filename, content, commit_msg):
    file_path = wc_dir / filename
    is_new = not file_path.exists()
    
    with open(file_path, "w") as f:
        f.write(content)
        
    if is_new:
        subprocess.run([SVN_BIN, "add", filename], cwd=wc_dir, check=True)
        
    subprocess.run([SVN_BIN, "commit", "-m", commit_msg], cwd=wc_dir, check=True)
    subprocess.run([SVN_BIN, "update"], cwd=wc_dir, check=True)
    
    # Grab the current revision string
    res = subprocess.run([SVN_BIN, "info", "--show-item", "revision"], cwd=wc_dir, capture_output=True, text=True, check=True)
    return res.stdout.strip()

def rename_file_svn(wc_dir, old_name, new_name, commit_msg):
    subprocess.run([SVN_BIN, "mv", old_name, new_name], cwd=wc_dir, check=True)
    subprocess.run([SVN_BIN, "commit", "-m", commit_msg], cwd=wc_dir, check=True)
    subprocess.run([SVN_BIN, "update"], cwd=wc_dir, check=True)
    res = subprocess.run([SVN_BIN, "info", "--show-item", "revision"], cwd=wc_dir, capture_output=True, text=True, check=True)
    return res.stdout.strip()

def create_mock_metadata(metadata_dir, commit_id, file_name, line_num, gen_ratio):
    with open(metadata_dir / f"{commit_id}.json", "w") as f:
        json.dump({
            "REPOSITORY": {"revisionId": commit_id, "repoURL": "mock://repo"},
            "DETAIL": [{"fileName": file_name, "codeLines": [{"lineLocation": line_num, "genRatio": gen_ratio}]}]
        }, f)

def run_native_cli_svn(wc_dir, metadata_dir, start="2000-01-01T00:00:00Z", end="2099-12-31T23:59:59Z"):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(wc_dir.parent.parent) 
    
    script_path = os.path.abspath("aggregateGenCodeDesc.py")
    
    result = subprocess.run([
        "python", script_path,
        "--repoURL", "mock://repo",
        "--repoBranch", "trunk",
        "--startTime", start,
        "--endTime", end,
        "--genCodeDescDir", str(metadata_dir),
        "--alg", "A",
        "--log-level", "DEBUG"
    ], cwd=wc_dir, capture_output=True, text=True)
    
    assert result.returncode == 0, f"Failed: {result.stderr}"
    return json.loads(result.stdout), result.stderr

def test_svn_native_blame_extraction(tmp_path):
    """
    Test native routing of SVN blame execution correctly resolves SVN XML tags
    and connects genCodeDesc JSON data physically!
    """
    wc = setup_svn_repo(tmp_path)
    rev1 = commit_file_svn(wc, "utils.py", "def x():\n    pass\n", "Initial SVN commit")
    
    m_dir = tmp_path / "metadata"
    m_dir.mkdir()
    
    # Inject that rev1's utils.py line 1 is fully AI!
    create_mock_metadata(m_dir, rev1, "utils.py", 1, 100)
    
    out, stderr = run_native_cli_svn(wc, m_dir)
    
    assert "Starting Native SVN AlgA (Live Blame) extraction..." in stderr
    assert out["SUMMARY"]["totalLines"] == 2
    assert out["SUMMARY"]["weightedModeRatio"] == 50.0

def test_svn_rename_tracing(tmp_path):
    """
    US-007 tests physical string parsing, this tests structural rename mapping via svn mv -> svn blame
    """
    wc = setup_svn_repo(tmp_path)
    
    rev1 = commit_file_svn(wc, "old.txt", "line1\nline2\n", "Create old.txt")
    rev2 = rename_file_svn(wc, "old.txt", "new.txt", "Rename old to new")
    
    m_dir = tmp_path / "metadata"
    m_dir.mkdir()
    
    # SVN Blame actually associates `svn mv` copied lines with the ORIGINAL filename at REVISION 1
    # Actually wait! SVN blame outputs the CURRENT path in its UI (or the query path), but the `<target path="new.txt">`. 
    # But does svn blame `--xml` output the ORIGINAL filename at the origin revision?
    # NO! Subversion's blame natively ONLY outputs the revision string of origin. It does NOT trace original filenames explicitly in the same way `git blame -M` provides `filename: old_name`.
    # As per AC-007-4, SVN limitations exist. We will just map it natively using what SVN spits out, validating the script gracefully parses `<target>` and attributes!
    # Because SVN blame XML says: `<target path="new.txt"><entry...><commit revision="1">...`
    # Our script uses fileName: `new.txt`. So we must put `new.txt` in the metadata, OR we accept it defaults to 0.0!
    
    # Let's map exactly how the script extracts it (it uses `f` which is `new.txt`).
    create_mock_metadata(m_dir, rev1, "new.txt", 1, 100)
    
    out, stderr = run_native_cli_svn(wc, m_dir)
    assert out["SUMMARY"]["weightedModeRatio"] == 50.0
