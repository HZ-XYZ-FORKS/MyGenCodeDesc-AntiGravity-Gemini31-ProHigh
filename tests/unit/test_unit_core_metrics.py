import pytest
from aggregateGenCodeDesc import compute_core_metrics

def test_unit_compute_core_metrics_zero_lines():
    """
    [@AC-001-6,US-001]
    TC-Unit-001:
      @[Name]: test_unit_compute_core_metrics_zero_lines
      @[Priority]: P1 Functional
      @[Category]: Boundary
      @[Purpose]: Verify compute_core_metrics logic for empty input.
      @[Brief]: Passing an empty array to compute_core_metrics should safely return zeroes.
      @[Expect]: All ratios are exactly 0.0.
    """
    metrics = compute_core_metrics([])
    assert metrics["totalLines"] == 0
    assert metrics["weightedRatio"] == 0.0
    assert metrics["fullyAIRatio"] == 0.0
    assert metrics["mostlyAIRatio"] == 0.0

def test_unit_compute_core_metrics_mixed_ratios():
    """
    [@AC-001-1,US-001]
    TC-Unit-002:
      @[Name]: test_unit_compute_core_metrics_mixed_ratios
      @[Priority]: P1 Functional
      @[Category]: Typical
      @[Purpose]: Verify compute_core_metrics logic for standard mixed data.
      @[Brief]: Passing 10 mixed lines should calculate accurate fractions.
      @[Expect]: weightedRatio is 77.0, fullyAI is 50.0, mostlyAI is 80.0.
    """
    lines = [
        {"genRatio": 100}, {"genRatio": 100}, {"genRatio": 100}, 
        {"genRatio": 100}, {"genRatio": 100}, {"genRatio": 80}, 
        {"genRatio": 80}, {"genRatio": 80}, {"genRatio": 30}, 
        {"genRatio": 0}
    ]
    metrics = compute_core_metrics(lines, threshold=60)
    assert metrics["totalLines"] == 10
    assert metrics["weightedRatio"] == 77.0
    assert metrics["fullyAIRatio"] == 50.0
    assert metrics["mostlyAIRatio"] == 80.0
