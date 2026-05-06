import os
import coverage

if "COVERAGE_PROCESS_START" in os.environ:
    coverage.process_startup()
