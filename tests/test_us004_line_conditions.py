def test_ac_004_line_conditions(vcs):
    content = "a" + chr(10) + " " + chr(10) + "\t" + chr(10) + chr(10)
    vcs.commit_file("app.py", content, "init", metadata_map={1: 100})
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 4
