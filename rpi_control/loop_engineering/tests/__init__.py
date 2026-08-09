"""
Loop Engineering Comprehensive Test Suite.

Modules:
- enhanced_test_data: Comprehensive test data generation (8 dimensions)
- enhanced_screening: Multi-round data screening with self-inspection
- real_training_pipeline: Real model training (replaces simulated runner)
- enhanced_loop: Enhanced loop engineering with convergence detection
- rpi_deep_check: Deep Raspberry Pi compatibility checker
- run_comprehensive_tests: Orchestrator for all test phases
"""

from .enhanced_test_data import (
    EnhancedTestDataGenerator,
    generate_all_test_data,
)
from .enhanced_screening import (
    EnhancedScreener,
    run_enhanced_screening,
)
from .real_training_pipeline import (
    RealTrainingPipeline,
    run_real_training,
)
from .enhanced_loop import (
    EnhancedLoopRunner,
    run_enhanced_loop,
)
from .rpi_deep_check import (
    RPiDeepChecker,
    run_rpi_deep_check,
)
from .run_comprehensive_tests import (
    ComprehensiveTestSuite,
    run_comprehensive_tests,
)

__all__ = [
    "EnhancedTestDataGenerator",
    "generate_all_test_data",
    "EnhancedScreener",
    "run_enhanced_screening",
    "RealTrainingPipeline",
    "run_real_training",
    "EnhancedLoopRunner",
    "run_enhanced_loop",
    "RPiDeepChecker",
    "run_rpi_deep_check",
    "ComprehensiveTestSuite",
    "run_comprehensive_tests",
]