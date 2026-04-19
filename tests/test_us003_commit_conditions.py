import pytest

def test_ac_003_1_single_commit(vcs):
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c1", 1775000000, "2026-03-31T00:00:00Z", {1: 100, 2:100})
    out = vcs.run_aggregator(start="2026-01-01T00:00:00Z", end="2026-12-31T00:00:00Z")
    if vcs.vcs_type == "git": 
        assert out["SUMMARY"]["totalLines"] == 2

def test_ac_003_2_multiple_commits(vcs):
    vcs.commit_file("app.py", "a" + chr(10), "c1", metadata_map={1: 100})
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c2", metadata_map={2: 50})
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 2
    assert out["SUMMARY"]["weightedModeRatio"] == 75.0

def test_ac_003_3_commit_bounds(vcs):
    if vcs.vcs_type == "svn":
        pytest.skip("SVN timeline bounding naturally relies on system server time which cannot be mocked via epochs")
    vcs.commit_file("a.py", "a" + chr(10), "c1", 1700000000, "2023-01-01T00:00:00Z", {1:100})
    vcs.commit_file("b.py", "b" + chr(10), "c2", 1776000000, "2026-06-01T00:00:00Z", {1:50})
    out = vcs.run_aggregator(start="2026-01-01T00:00:00Z", end="2026-12-31T00:00:00Z")
    assert out["SUMMARY"]["totalLines"] == 1 
    assert out["SUMMARY"]["weightedModeRatio"] == 50.0
