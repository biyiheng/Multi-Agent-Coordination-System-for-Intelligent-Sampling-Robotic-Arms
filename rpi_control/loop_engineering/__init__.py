"""
Loop Engineering Framework for the Multi-Agent System.

Provides performance profiling, interaction tracking, multi-dimensional
evaluation, context management, skill extraction, and automated optimization
loop (propose → train/execute → evaluate → keep/revert).

Modules:
    profiler: Agent-level and end-to-end latency measurement.
    interaction_tracker: Agent interaction counting and redundancy detection.
    evaluator: Multi-dimensional evaluation across 7 metric dimensions.
    context_manager: State persistence, history compression, decay detection.
    skill_extractor: Reusable skill extraction from execution traces.
    knowledge_inheritor: Cross-generation knowledge transfer.
    meta_optimizer: Optimization of the optimization algorithm itself.
    loop_runner: Main loop orchestrating the full engineering cycle.
"""

__version__ = "1.0.0"