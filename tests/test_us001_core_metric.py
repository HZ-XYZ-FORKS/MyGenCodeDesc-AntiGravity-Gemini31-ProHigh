def test_ac_001_1_weighted_mode(vcs):
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 77.0

def test_ac_001_2_fully_ai_mode(vcs):
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["fullyAIModeRatio"] == 50.0

def test_ac_001_3_mostly_ai_mode(vcs):
    content = chr(10).join([f"line_{i}" for i in range(10)]) + chr(10)
    meta = {i+1: ratio for i, ratio in enumerate([100, 100, 100, 100, 100, 80, 80, 80, 30, 0])}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator(threshold=60)
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 80.0

def test_ac_001_4_all_human(vcs):
    content = chr(10).join([f"line_{i}" for i in range(50)]) + chr(10)
    meta = {i+1: 0 for i in range(50)}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 0.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 0.0

def test_ac_001_5_all_ai(vcs):
    content = chr(10).join([f"line_{i}" for i in range(50)]) + chr(10)
    meta = {i+1: 100 for i in range(50)}
    
    vcs.commit_file("app.py", content, "Init", metadata_map=meta)
    
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["weightedModeRatio"] == 100.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 100.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 100.0

def test_ac_001_6_no_lines(vcs):
    out = vcs.run_aggregator()
    assert out["SUMMARY"]["totalLines"] == 0
    assert out["SUMMARY"]["weightedModeRatio"] == 0.0
    assert out["SUMMARY"]["fullyAIModeRatio"] == 0.0
    assert out["SUMMARY"]["mostlyAIModeRatio"] == 0.0
