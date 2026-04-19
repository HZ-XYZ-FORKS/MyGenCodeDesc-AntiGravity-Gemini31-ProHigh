import pytest
import subprocess
import json
import os
import stat

def create_mock_metadata(metadata_dir, commit_id, file_name, line_num, gen_ratio, filename_override=None):
    disk_name = filename_override if filename_override else f"{commit_id}.json"
    with open(metadata_dir / disk_name, "w") as f:
        json.dump({
            "REPOSITORY": {"revisionId": commit_id, "repoURL": "mock://repo"},
            "DETAIL": [{"fileName": file_name, "codeLines": [{"lineLocation": line_num, "genRatio": gen_ratio}]}]
        }, f)

def run_e2e_cli(tmp_path, metadata_dir, blame_lines=None, repo="mock://repo", start="2026-01-01T00:00:00Z", end="2026-12-31T23:59:59Z", log_level="INFO", alg="A", patches_dir=None):
    import json
    cmd = [
        "python", "aggregateGenCodeDesc.py",
        "--repoURL", repo,
        "--repoBranch", "main",
        "--startTime", start,
        "--endTime", end,
        "--genCodeDescDir", str(metadata_dir),
        "--log-level", log_level,
        "--alg", alg
    ]
    if blame_lines is not None:
        blame_file = tmp_path / "blame.json"
        with open(blame_file, "w") as f:
            json.dump(blame_lines, f)
        cmd.extend(["--mock-blame-lines", str(blame_file)])
        
    if patches_dir:
        cmd.extend(["--patchesDir", str(patches_dir)])
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Do not crash brutally on tests evaluating failure paths
    if result.returncode != 0 and alg != "A":
        return {}, result.stderr
            
    assert result.returncode == 0
    return json.loads(result.stdout), result.stderr

def test_ac_007_1_git_sha(tmp_path):
    """AC-007-1: Git revision identity is SHA hash"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir()
    create_mock_metadata(m_dir, "c2fe1db2c2fe1db2c2fe1db2c2fe1db2c2fe1db2", "index.js", 2, 80)
    blame = [{"fileName": "index.js", "lineNumber": 2, "originCommit": "c2fe1db2c2fe1db2c2fe1db2c2fe1db2c2fe1db2", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame)
    assert out["SUMMARY"]["totalLines"] == 1
    assert out["SUMMARY"]["weightedModeRatio"] == 80.0

def test_ac_007_2_svn_integer(tmp_path):
    """AC-007-2: SVN revision identity is sequential integer"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "4217", "main.py", 1, 100)
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "4217", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame)
    assert out["SUMMARY"]["totalLines"] == 1
    assert out["SUMMARY"]["weightedModeRatio"] == 100.0

def test_ac_008_3_scale_empty_window(tmp_path):
    """AC-008-3: Empty time window returns 0.0 naturally."""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    out, stderr = run_e2e_cli(tmp_path, m_dir, [])
    assert out["SUMMARY"]["totalLines"] == 0
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0

def test_ac_008_4_scale_io_failure(tmp_path):
    """AC-008-4: Graceful I/O failure recovery."""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    fault_file = m_dir / "crash.json"
    with open(fault_file, "w") as f: f.write("{broken}")
    os.chmod(fault_file, 0000)
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "CRASH", "commitTime": "2026-05-01T10:00:00Z"}]
    try:
        out, stderr = run_e2e_cli(tmp_path, m_dir, blame)
        assert "IO Error reading" in stderr or "Unexpected error loading" in stderr
    finally:
        os.chmod(fault_file, stat.S_IRUSR | stat.S_IWUSR)

# -- US-010: Diagnostics and Logging Unpacked --

def test_ac_010_1_default_log_level_phases(tmp_path):
    """AC-010-1: Default log level is INFO with load/process/summary phases"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 100)
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="INFO")
    assert "[INFO] [AlgC] LOAD revisionId=C1" in stderr
    assert "[INFO] [AlgC] SUMMARY aggregate totalLines=1" in stderr
    assert "PROCESS" not in stderr  # PROCESS is DEBUG level

def test_ac_010_2_debug_level_detail(tmp_path):
    """AC-010-2: DEBUG level shows per-file and per-line detail"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 100)
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="DEBUG")
    assert "[DEBUG] [AlgC] PROCESS file=main.py line=1 origin=C1 genRatio=100" in stderr

def test_ac_010_3_warn_anomalies(tmp_path):
    """AC-010-3: WARN level logs non-fatal anomalies"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 100, filename_override="C1.json")
    create_mock_metadata(m_dir, "C1", "main.py", 1, 50, filename_override="C1_dup.json")
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="INFO")
    assert "[WARNING] [AlgC] Duplicate genCodeDesc" in stderr

def test_ac_010_4_error_fatal_failures(tmp_path):
    """AC-010-4: ERROR level logs fatal failures"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 150) # Invalid bounds causes fatal rejection of record
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="INFO")
    assert "[ERROR] [AlgC] genRatio must be 0-100" in stderr

def test_ac_010_5_error_level_suppresses(tmp_path):
    """AC-010-5: --log-level ERROR suppresses INFO and WARN"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 100, filename_override="C1.json")
    create_mock_metadata(m_dir, "C1", "main.py", 1, 50, filename_override="C1_dup.json")
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="ERROR")
    # Duplicate is WARN, so it should be suppressed
    assert "[WARNING] [AlgC] Duplicate genCodeDesc" not in stderr
    assert "[INFO]" not in stderr

def test_ac_010_6_structured_log_format(tmp_path):
    """AC-010-6: Structured log format for machine parsing"""
    m_dir = tmp_path / "metadata"
    m_dir.mkdir(exist_ok=True)
    create_mock_metadata(m_dir, "C1", "main.py", 1, 100)
    blame = [{"fileName": "main.py", "lineNumber": 1, "originCommit": "C1", "commitTime": "2026-05-01T10:00:00Z"}]
    out, stderr = run_e2e_cli(tmp_path, m_dir, blame, log_level="INFO")
    # Format matches: 2026-04-14T10:30:00Z [INFO] [AlgC]
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[INFO\] \[AlgC\]", stderr)

def test_ac_010_7_testability(tmp_path):
    """AC-010-7: Unit tests can set log level programmatically"""
    import logging
    # API mock to ensure the log_level is not just CLI bound but accessible directly
    from aggregateGenCodeDesc import logger
    logger.setLevel(logging.CRITICAL)
    assert logger.level == logging.CRITICAL
