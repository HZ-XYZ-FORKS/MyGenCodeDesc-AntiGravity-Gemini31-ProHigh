def test_ac_005_duplicate_conflict(vcs):
    """
    [@AC-005-1,US-005]
    TC-Sys-0051:
      @[Name]: test_ac_005_duplicate_conflict
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_005_duplicate_conflict
      @[Brief]: Systematically tests the test_ac_005_duplicate_conflict behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c1", metadata_map={1: 100, 2: 50})
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 2
