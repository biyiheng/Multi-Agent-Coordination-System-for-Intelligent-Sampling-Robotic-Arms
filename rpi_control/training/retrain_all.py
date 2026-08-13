"""
Controlled full retraining driver.

Trains all four ML models (motion_ik, safety, quality, collision) on the freshly
regenerated Round 12 datasets (workspace-aligned 0~500,0~500,0~300 + hand-eye
coordinate transform fix + collision boundary rule alignment). Single consolidated
pass with moderate epochs.

Usage:
    python -m training.retrain_all
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from training.model_trainer import ModelTrainer
from training import monitor_recall


def main() -> None:
    trainer = ModelTrainer()
    overall = time.time()

    print("=" * 60)
    print("  RETRAIN ALL (Round 12 data + coordinate + collision fixes)")
    print("=" * 60)

    specs = [
        ("motion_ik", lambda: trainer.train_motion_model(epochs=200)),
        ("safety", lambda: trainer.train_safety_model(epochs=250)),
        ("quality", lambda: trainer.train_quality_model(epochs=300)),
        # Round 12: rule-aligned boundary (radius+30) + eff_radius/clearance features.
        ("collision", lambda: trainer.train_collision_model(epochs=150, n_ensemble=5)),
    ]
    for name, fn in specs:
        t0 = time.time()
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [ERROR] {name}: {e}")
        print(f"  [{name}] elapsed {time.time()-t0:.1f}s")

    trainer.save_results()

    # Round 12: automatic recall gate — fail the run if the collision model's
    # recall regressed below 0.85 (safety-critical). Non-zero exit blocks CI.
    print("\n--- Monitoring recall gate ---")
    gate_exit = monitor_recall.main(["--model", "collision", "--threshold", "0.85"])
    print(f"  recall gate exit code: {gate_exit}")
    print(f"\n  TOTAL: {time.time()-overall:.1f}s")
    if gate_exit != 0:
        sys.exit(gate_exit)


if __name__ == "__main__":
    main()
