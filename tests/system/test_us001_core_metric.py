def test_ac_001_1_weighted_mode(vcs):
    """
    [@AC-001-1,US-001]
    TC-Sys-0011:
      @[Name]: test_ac_001_1_weighted_mode
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_1_weighted_mode
      @[Brief]: Systematically tests the test_ac_001_1_weighted_mode behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 77.0

def test_ac_001_2_fully_ai_mode(vcs):
    """
    [@AC-001-2,US-001]
    TC-Sys-0012:
      @[Name]: test_ac_001_2_fully_ai_mode
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_2_fully_ai_mode
      @[Brief]: Systematically tests the test_ac_001_2_fully_ai_mode behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["fullyAIModeRatio"] == 50.0

def test_ac_001_3_mostly_ai_mode(vcs):
    """
    [@AC-001-3,US-001]
    TC-Sys-0013:
      @[Name]: test_ac_001_3_mostly_ai_mode
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_3_mostly_ai_mode
      @[Brief]: Systematically tests the test_ac_001_3_mostly_ai_mode behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator(threshold=60)
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 80.0

def test_ac_001_4_all_human(vcs):
    """
    [@AC-001-4,US-001]
    TC-Sys-0014:
      @[Name]: test_ac_001_4_all_human
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_4_all_human
      @[Brief]: Systematically tests the test_ac_001_4_all_human behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = chr(10).join([f"line_{i}" for i in range(50)]) + chr(10)
    meta = {i+1: 0 for i in range(50)}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 0.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 0.0

def test_ac_001_5_all_ai(vcs):
    """
    [@AC-001-5,US-001]
    TC-Sys-0015:
      @[Name]: test_ac_001_5_all_ai
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_5_all_ai
      @[Brief]: Systematically tests the test_ac_001_5_all_ai behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    content = chr(10).join([f"line_{i}" for i in range(50)]) + chr(10)
    meta = {i+1: 100 for i in range(50)}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 100.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 100.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 100.0

def test_ac_001_6_no_lines(vcs):
    """
    [@AC-001-6,US-001]
    TC-Sys-0016:
      @[Name]: test_ac_001_6_no_lines
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify test_ac_001_6_no_lines
      @[Brief]: Systematically tests the test_ac_001_6_no_lines behavior.
      @[Expect]: Test passes and adheres to conditions.
    """
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 0
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 0.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 0.0
