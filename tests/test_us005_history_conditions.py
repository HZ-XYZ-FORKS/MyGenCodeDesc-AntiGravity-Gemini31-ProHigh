def test_ac_005_duplicate_conflict(vcs):
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c1", metadata_map={1: 100, 2: 50})
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 2
