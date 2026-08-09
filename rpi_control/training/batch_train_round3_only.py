"""
Batch Training Script - Round 3 Only (Final Precision & Stability Tuning).

Run only Round 3 with the fixed epochs parameter passing.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Enable line buffering for real-time output
sys.stdout.reconfigure(line_buffering=True)

from training.data_generator import DatasetGenerator
from training.model_trainer import ModelTrainer


# Round 3 config only
ROUND_CONFIG = {
    "round": 3,
    "name": "Final Precision & Stability Tuning",
    "description": "Maximum epochs, best ensemble, strict regularization",
    "motion_epochs": 1000,
    "safety_epochs": 1000,
    "quality_epochs": 2000,
    "collision_epochs": 600,
    "collision_ensemble": 11,
}

ERROR_THRESHOLDS = {
    "motion": {"max_mae_deg": 10.0, "min_r2": 0.90},
    "safety": {"min_f1": 0.92, "min_precision": 0.88},
    "quality": {"min_r2": 0.85, "max_mae": 8.0},
    "collision": {"min_f1": 0.90, "min_precision": 0.85},
}

BEST_KNOWN = {
    "motion": {"r2_score": 0.9898, "mae": 0.0852},
    "safety": {"f1_score": 0.9736, "precision": 0.9592, "recall": 0.9885},
    "quality": {"r2_score": 0.9925, "mae": 2.35, "accuracy": 0.9608},
    "collision": {"f1_score": 0.9591, "precision": 0.9284, "recall": 0.9920},
}


def print_header(text: str) -> None:
    print("\n" + "=" * 70, flush=True)
    print(f"  {text}", flush=True)
    print("=" * 70, flush=True)


def print_subheader(text: str) -> None:
    print(f"\n  --- {text} ---", flush=True)


def check_results(results: Dict[str, Any]) -> List[str]:
    """Check training results against error thresholds."""
    warnings = []
    for model_name, thresholds in ERROR_THRESHOLDS.items():
        if model_name not in results:
            continue
        metrics = results[model_name]
        if model_name == "motion":
            mae_deg = metrics.get("mae", 0) * 180 / 3.14159
            r2 = metrics.get("r2_score", 0)
            if mae_deg > thresholds["max_mae_deg"]:
                warnings.append(f"⚠️  Motion MAE too high: {mae_deg:.1f}° > {thresholds['max_mae_deg']}°")
            if r2 < thresholds["min_r2"]:
                warnings.append(f"⚠️  Motion R² too low: {r2:.4f} < {thresholds['min_r2']}")
        elif model_name == "safety":
            f1 = metrics.get("f1_score", 0)
            prec = metrics.get("precision", 0)
            if f1 < thresholds["min_f1"]:
                warnings.append(f"⚠️  Safety F1 too low: {f1:.4f} < {thresholds['min_f1']}")
            if prec < thresholds["min_precision"]:
                warnings.append(f"⚠️  Safety Precision too low: {prec:.4f} < {thresholds['min_precision']}")
        elif model_name == "quality":
            r2 = metrics.get("r2_score", 0)
            mae = metrics.get("mae", 0)
            if r2 < thresholds["min_r2"]:
                warnings.append(f"⚠️  Quality R² too low: {r2:.4f} < {thresholds['min_r2']}")
            if mae > thresholds["max_mae"]:
                warnings.append(f"⚠️  Quality MAE too high: {mae:.2f} > {thresholds['max_mae']}")
        elif model_name == "collision":
            f1 = metrics.get("f1_score", 0)
            prec = metrics.get("precision", 0)
            if f1 < thresholds["min_f1"]:
                warnings.append(f"⚠️  Collision F1 too low: {f1:.4f} < {thresholds['min_f1']}")
            if prec < thresholds["min_precision"]:
                warnings.append(f"⚠️  Collision Precision too low: {prec:.4f} < {thresholds['min_precision']}")
    return warnings


def compare_with_best_known(current: Dict[str, Any]) -> Dict[str, Any]:
    """Compare with best known results."""
    comparison = {}
    for model_name in BEST_KNOWN:
        if model_name not in current:
            continue
        curr = current[model_name]
        best = BEST_KNOWN[model_name]
        changes = {"status": "comparing"}
        if model_name == "motion":
            r2_delta = curr.get("r2_score", 0) - best["r2_score"]
            mae_delta = curr.get("mae", 0) - best["mae"]
            changes["r2_vs_best"] = round(r2_delta, 4)
            changes["mae_vs_best"] = round(mae_delta, 4)
            if r2_delta > 0.001 and mae_delta < 0:
                changes["status"] = "improved"
            elif r2_delta < -0.005 or mae_delta > 0.01:
                changes["status"] = "degraded"
            else:
                changes["status"] = "comparable"
        elif model_name == "safety":
            f1_delta = curr.get("f1_score", 0) - best["f1_score"]
            prec_delta = curr.get("precision", 0) - best["precision"]
            changes["f1_vs_best"] = round(f1_delta, 4)
            changes["prec_vs_best"] = round(prec_delta, 4)
            if f1_delta > 0.002 and prec_delta > 0.001:
                changes["status"] = "improved"
            elif f1_delta < -0.005 or prec_delta < -0.01:
                changes["status"] = "degraded"
            else:
                changes["status"] = "comparable"
        elif model_name == "quality":
            r2_delta = curr.get("r2_score", 0) - best["r2_score"]
            mae_delta = curr.get("mae", 0) - best["mae"]
            changes["r2_vs_best"] = round(r2_delta, 4)
            changes["mae_vs_best"] = round(mae_delta, 4)
            if r2_delta > 0.001 and mae_delta < 0:
                changes["status"] = "improved"
            elif r2_delta < -0.005 or mae_delta > 1.0:
                changes["status"] = "degraded"
            else:
                changes["status"] = "comparable"
        elif model_name == "collision":
            f1_delta = curr.get("f1_score", 0) - best["f1_score"]
            prec_delta = curr.get("precision", 0) - best["precision"]
            changes["f1_vs_best"] = round(f1_delta, 4)
            changes["prec_vs_best"] = round(prec_delta, 4)
            if f1_delta > 0.002 and prec_delta > 0.001:
                changes["status"] = "improved"
            elif f1_delta < -0.005 or prec_delta < -0.01:
                changes["status"] = "degraded"
            else:
                changes["status"] = "comparable"
        comparison[model_name] = changes
    return comparison


def main():
    print_header("ROUND 3 ONLY: Final Precision & Stability Tuning")
    print(f"  {ROUND_CONFIG['description']}")
    print(f"  Motion: {ROUND_CONFIG['motion_epochs']} epochs")
    print(f"  Safety: {ROUND_CONFIG['safety_epochs']} epochs")
    print(f"  Quality: {ROUND_CONFIG['quality_epochs']} epochs")
    print(f"  Collision: {ROUND_CONFIG['collision_epochs']} epochs, {ROUND_CONFIG['collision_ensemble']} ensemble")
    total_start = time.time()

    # Phase 1: Data Generation & Cleaning
    print_subheader("Phase 1: Data Generation, Cleaning & Preprocessing")
    generator = DatasetGenerator(seed=42 + 2 * 13)  # Round 3 seed
    counts = generator.save_all_datasets()
    total_samples = sum(counts.values())
    print(f"\n  Total datasets: {len(counts)}, Total samples: {total_samples}")

    # Phase 2: Model Training
    print_subheader("Phase 2: Model Training with Real-time Monitoring")
    trainer = ModelTrainer()

    # Train motion model
    print(f"\n  [Motion Model] Round 3 - {ROUND_CONFIG['name']}")
    print(f"  Config: epochs={ROUND_CONFIG['motion_epochs']}")
    motion_start = time.time()
    motion_metrics = trainer.train_motion_model(epochs=ROUND_CONFIG['motion_epochs'])
    motion_time = time.time() - motion_start
    print(f"  Motion training time: {motion_time:.1f}s ({motion_time/60:.1f} min)")

    # Train safety model
    print(f"\n  [Safety Model] Round 3 - {ROUND_CONFIG['name']}")
    print(f"  Config: epochs={ROUND_CONFIG['safety_epochs']}")
    safety_start = time.time()
    safety_metrics = trainer.train_safety_model(epochs=ROUND_CONFIG['safety_epochs'])
    safety_time = time.time() - safety_start
    print(f"  Safety training time: {safety_time:.1f}s ({safety_time/60:.1f} min)")

    # Train quality model
    print(f"\n  [Quality Model] Round 3 - {ROUND_CONFIG['name']}")
    print(f"  Config: epochs={ROUND_CONFIG['quality_epochs']}")
    quality_start = time.time()
    quality_metrics = trainer.train_quality_model(epochs=ROUND_CONFIG['quality_epochs'])
    quality_time = time.time() - quality_start
    print(f"  Quality training time: {quality_time:.1f}s ({quality_time/60:.1f} min)")

    # Train collision model
    print(f"\n  [Collision Model] Round 3 - {ROUND_CONFIG['name']}")
    print(f"  Config: epochs={ROUND_CONFIG['collision_epochs']}, ensemble={ROUND_CONFIG['collision_ensemble']}")
    collision_start = time.time()
    collision_metrics = trainer.train_collision_model(
        epochs=ROUND_CONFIG['collision_epochs'],
        n_ensemble=ROUND_CONFIG['collision_ensemble'],
    )
    collision_time = time.time() - collision_start
    print(f"  Collision training time: {collision_time:.1f}s ({collision_time/60:.1f} min)")

    # Save results
    trainer.save_results()

    # Phase 3: Result Analysis
    print_subheader("Phase 3: Result Analysis")
    current_results = {}
    for name, metrics in trainer.results.items():
        current_results[name] = {
            "model_name": metrics.model_name,
            "train_loss": metrics.train_loss,
            "val_loss": metrics.val_loss,
            "accuracy": metrics.accuracy,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "r2_score": metrics.r2_score,
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "train_time_s": metrics.train_time_s,
            "num_params": metrics.num_params,
            "convergence_epoch": metrics.convergence_epoch,
        }

    # Check thresholds
    warnings = check_results(current_results)
    if warnings:
        print("\n  ⚠️  WARNINGS:")
        for w in warnings:
            print(f"    {w}")
    else:
        print("\n  ✅ All metrics within acceptable thresholds!")

    # Compare with best known
    print("\n  Comparison with Best Known (Round 2):")
    comparison = compare_with_best_known(current_results)
    for model_name, changes in comparison.items():
        status_icon = {"improved": "✅", "degraded": "❌", "comparable": "➡️", "comparing": "➡️"}
        icon = status_icon.get(changes.get("status", "comparing"), "➡️")
        print(f"    {icon} {model_name}: {changes.get('status', 'unknown')}")
        for k, v in changes.items():
            if k != "status" and isinstance(v, float):
                direction = "↑" if v > 0 else "↓" if v < 0 else "→"
                print(f"       {k}: {direction}{abs(v):.4f}")

    # Print summary
    print_header("Round 3 Training Complete")
    total_time = time.time() - total_start
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"\n  Final Results:")
    for name, metrics in trainer.results.items():
        r2_str = f"R²={metrics.r2_score:.4f}" if metrics.r2_score != 0 else ""
        f1_str = f"F1={metrics.f1_score:.4f}" if metrics.f1_score != 0 else ""
        prec_str = f"Prec={metrics.precision:.4f}" if metrics.precision != 0 else ""
        extras = " ".join(filter(None, [r2_str, f1_str, prec_str]))
        print(f"    {name:15s}: {extras}")


if __name__ == "__main__":
    main()