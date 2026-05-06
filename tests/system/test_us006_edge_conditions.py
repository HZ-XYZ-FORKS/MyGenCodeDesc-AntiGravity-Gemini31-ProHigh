def test_ac_006_fault(vcs):
    """
    [@AC-006-1,US-006]
    TC-Sys-0061:
      @[Name]: test_ac_006_fault
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_006_fault
      @[Brief]: Systematically tests the test_ac_006_fault behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    vcs.commit_file("app.py", "a" + chr(10) + "b" + chr(10), "c1", metadata_map=None)
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 2
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
