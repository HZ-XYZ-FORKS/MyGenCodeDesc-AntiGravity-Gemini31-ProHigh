def test_ac_004_line_conditions(vcs):
    """
    [@AC-004-1,US-004]
    TC-Sys-0041:
      @[Name]: test_ac_004_line_conditions
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_004_line_conditions
      @[Brief]: Systematically tests the test_ac_004_line_conditions behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = "a" + chr(10) + " " + chr(10) + "\t" + chr(10) + chr(10)
    vcs.commit_file("app.py", content, "init", metadata_map={1: 100})
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 4
