def test_ac_006_fault(vcs):
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c1", metadata_map=None)
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 2
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
