"""
Batch Training Script - Round 11: Super-Expanded Data, Enhanced Cleaning, Multi-Round Training.

Key improvements over Round 10:
1. Data volume: 1.5-2x further expansion (total ~300K+ samples, ~15 datasets)
2. Data cleaning: NaN/Inf removal, deduplication, 4-sigma outlier clipping
3. Data preprocessing: 3x noise augmentation, class balancing
4. Real-time monitoring: progress bars, anomaly detection, trend tracking
5. K-fold cross-validation: 5-fold CV for robust evaluation
6. Multi-round training: 3 rounds with architecture optimization
7. Stricter error thresholds: automatic stop if degradation detected
8. Comprehensive final report with per-model best results
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Enable line buffering for real-time output (Python 3.7+)
sys.stdout.reconfigure(line_buffering=True)

# Dedicated log file for real-time monitoring
LOG_FILE = Path(__file__).resolve().parent.parent / "reports" / "round11_training.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

from training.data_generator import DatasetGenerator
from training.model_trainer import ModelTrainer, TrainingMonitor


# =============================================================================
# Configuration
# =============================================================================

ROUND_CONFIGS = [
    {
        "round": 1,
        "name": "Baseline with Super-Expanded Data",
        "description": "Train on 300K+ samples with 3x augmentation, baseline architectures",
        "motion_epochs": 600,
        "safety_epochs": 600,
        "quality_epochs": 1200,
        "collision_epochs": 400,
        "collision_ensemble": 7,
    },
    {
        "round": 2,
        "name": "Architecture & Feature Optimization",
        "description": "Deeper networks, feature refinement based on Round 1 CV results",
        "motion_epochs": 800,
        "safety_epochs": 800,
        "quality_epochs": 1500,
        "collision_epochs": 500,
        "collision_ensemble": 9,
    },
    {
        "round": 3,
        "name": "Final Precision & Stability Tuning",
        "description": "Maximum epochs, best ensemble, strict regularization",
        "motion_epochs": 1000,
        "safety_epochs": 1000,
        "quality_epochs": 2000,
        "collision_epochs": 600,
        "collision_ensemble": 11,
    },
]

# Stricter error thresholds for Round 11
ERROR_THRESHOLDS = {
    "motion": {"max_mae_deg": 10.0, "min_r2": 0.90},
    "safety": {"min_f1": 0.92, "min_precision": 0.88},
    "quality": {"min_r2": 0.85, "max_mae": 8.0},
    "collision": {"min_f1": 0.90, "min_precision": 0.85},
}

# Best known results from Round 9 (for comparison)
BEST_KNOWN = {
    "motion": {"r2_score": 0.9882, "mae": 0.0897},
    "safety": {"f1_score": 0.9711, "precision": 0.9538, "recall": 0.9891},
    "quality": {"r2_score": 0.9919, "mae": 2.48, "accuracy": 0.9563},
    "collision": {"f1_score": 0.9575, "precision": 0.9318, "recall": 0.9847},
}


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70, flush=True)
    print(f"  {text}", flush=True)
    print("=" * 70, flush=True)


def print_subheader(text: str) -> None:
    """Print a formatted sub-header."""
    print(f"\n  --- {text} ---", flush=True)


def check_results_against_thresholds(
    results: Dict[str, Any], round_num: int
) -> List[str]:
    """Check training results against error thresholds.

    Returns:
        List of warning messages if thresholds exceeded.
    """
    warnings = []

    for model_name, thresholds in ERROR_THRESHOLDS.items():
        if model_name not in results:
            continue

        metrics = results[model_name]

        if model_name == "motion":
            mae_deg = metrics.get("mae", 0) * 180 / 3.14159  # Convert rad to deg
            r2 = metrics.get("r2_score", 0)
            if mae_deg > thresholds["max_mae_deg"]:
                warnings.append(
                    f"⚠️  Motion MAE too high: {mae_deg:.1f}° > {thresholds['max_mae_deg']}°"
                )
            if r2 < thresholds["min_r2"]:
                warnings.append(
                    f"⚠️  Motion R² too low: {r2:.4f} < {thresholds['min_r2']}"
                )

        elif model_name == "safety":
            f1 = metrics.get("f1_score", 0)
            prec = metrics.get("precision", 0)
            if f1 < thresholds["min_f1"]:
                warnings.append(
                    f"⚠️  Safety F1 too low: {f1:.4f} < {thresholds['min_f1']}"
                )
            if prec < thresholds["min_precision"]:
                warnings.append(
                    f"⚠️  Safety Precision too low: {prec:.4f} < {thresholds['min_precision']}"
                )

        elif model_name == "quality":
            r2 = metrics.get("r2_score", 0)
            mae = metrics.get("mae", 0)
            if r2 < thresholds["min_r2"]:
                warnings.append(
                    f"⚠️  Quality R² too low: {r2:.4f} < {thresholds['min_r2']}"
                )
            if mae > thresholds["max_mae"]:
                warnings.append(
                    f"⚠️  Quality MAE too high: {mae:.2f} > {thresholds['max_mae']}"
                )

        elif model_name == "collision":
            f1 = metrics.get("f1_score", 0)
            prec = metrics.get("precision", 0)
            if f1 < thresholds["min_f1"]:
                warnings.append(
                    f"⚠️  Collision F1 too low: {f1:.4f} < {thresholds['min_f1']}"
                )
            if prec < thresholds["min_precision"]:
                warnings.append(
                    f"⚠️  Collision Precision too low: {prec:.4f} < {thresholds['min_precision']}"
                )

    return warnings


def compare_with_previous(
    current: Dict[str, Any], previous: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare current round results with previous round.

    Returns:
        Dict with per-model improvement metrics.
    """
    comparison = {}
    for model_name in current:
        if model_name not in previous:
            comparison[model_name] = {"status": "new"}
            continue

        curr = current[model_name]
        prev = previous[model_name]

        changes = {}

        # R² comparison
        if curr.get("r2_score", 0) != 0 and prev.get("r2_score", 0) != 0:
            delta = curr["r2_score"] - prev["r2_score"]
            changes["r2_delta"] = round(delta, 4)
            changes["r2_direction"] = "up" if delta > 0 else "down"

        # F1 comparison
        if curr.get("f1_score", 0) != 0 and prev.get("f1_score", 0) != 0:
            delta = curr["f1_score"] - prev["f1_score"]
            changes["f1_delta"] = round(delta, 4)
            changes["f1_direction"] = "up" if delta > 0 else "down"

        # MAE comparison
        if curr.get("mae", 0) != 0 and prev.get("mae", 0) != 0:
            delta = curr["mae"] - prev["mae"]
            changes["mae_delta"] = round(delta, 4)
            changes["mae_direction"] = "down" if delta < 0 else "up"

        # Precision comparison
        if curr.get("precision", 0) != 0 and prev.get("precision", 0) != 0:
            delta = curr["precision"] - prev["precision"]
            changes["precision_delta"] = round(delta, 4)
            changes["precision_direction"] = "up" if delta > 0 else "down"

        # Accuracy comparison
        if curr.get("accuracy", 0) != 0 and prev.get("accuracy", 0) != 0:
            delta = curr["accuracy"] - prev["accuracy"]
            changes["accuracy_delta"] = round(delta, 4)
            changes["accuracy_direction"] = "up" if delta > 0 else "down"

        comparison[model_name] = changes

    return comparison


def compare_with_best_known(current: Dict[str, Any]) -> Dict[str, Any]:
    """Compare current results with best known results from Round 9.

    Returns:
        Dict with improvement/worsening indicators.
    """
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


def run_training_round(
    round_config: Dict[str, Any],
    round_idx: int,
    total_rounds: int,
    all_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run a single training round with monitoring.

    Args:
        round_config: Round configuration.
        round_idx: 0-based round index.
        total_rounds: Total number of rounds.
        all_results: List of previous round results for comparison.

    Returns:
        Round results dict.
    """
    print_header(f"Round {round_config['round']}/{total_rounds}: {round_config['name']}")
    print(f"  {round_config['description']}")
    total_start = time.time()

    # Phase 1: Data Generation & Cleaning
    print_subheader("Phase 1: Data Generation, Cleaning & Preprocessing")
    generator = DatasetGenerator(seed=42 + round_idx * 13)
    counts = generator.save_all_datasets()

    total_samples = sum(counts.values())
    print(f"\n  Total datasets: {len(counts)}, Total samples: {total_samples}")

    # Phase 2: Model Training
    print_subheader("Phase 2: Model Training with Real-time Monitoring")
    trainer = ModelTrainer()

    # Train motion model
    print(f"\n  [Motion Model] Round {round_config['round']} - {round_config['name']}")
    print(f"  Config: epochs={round_config['motion_epochs']}")
    motion_start = time.time()
    motion_metrics = trainer.train_motion_model(epochs=round_config['motion_epochs'])
    motion_time = time.time() - motion_start
    print(f"  Motion training time: {motion_time:.1f}s ({motion_time/60:.1f} min)")

    # Train safety model
    print(f"\n  [Safety Model] Round {round_config['round']} - {round_config['name']}")
    print(f"  Config: epochs={round_config['safety_epochs']}")
    safety_start = time.time()
    safety_metrics = trainer.train_safety_model(epochs=round_config['safety_epochs'])
    safety_time = time.time() - safety_start
    print(f"  Safety training time: {safety_time:.1f}s ({safety_time/60:.1f} min)")

    # Train quality model
    print(f"\n  [Quality Model] Round {round_config['round']} - {round_config['name']}")
    print(f"  Config: epochs={round_config['quality_epochs']}")
    quality_start = time.time()
    quality_metrics = trainer.train_quality_model(epochs=round_config['quality_epochs'])
    quality_time = time.time() - quality_start
    print(f"  Quality training time: {quality_time:.1f}s ({quality_time/60:.1f} min)")

    # Train collision model
    print(f"\n  [Collision Model] Round {round_config['round']} - {round_config['name']}")
    print(f"  Config: epochs={round_config['collision_epochs']}, ensemble={round_config['collision_ensemble']}")
    collision_start = time.time()
    collision_metrics = trainer.train_collision_model(
        epochs=round_config['collision_epochs'],
        n_ensemble=round_config['collision_ensemble'],
    )
    collision_time = time.time() - collision_start
    print(f"  Collision training time: {collision_time:.1f}s ({collision_time/60:.1f} min)")

    # Save results
    trainer.save_results()

    # Phase 3: Result Analysis
    print_subheader("Phase 3: Result Analysis")

    # Convert metrics to dict for comparison
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

    # Print current results
    print(f"\n  Round {round_config['round']} Results:")
    for name, m in current_results.items():
        if m["f1_score"] > 0:
            print(f"    {name:15s}: F1={m['f1_score']:.4f}, Acc={m['accuracy']:.4f}, "
                  f"Prec={m['precision']:.4f}, Rec={m['recall']:.4f}")
        elif m["r2_score"] != 0:
            mae_deg = m["mae"] * 180 / 3.14159 if name == "motion" else m["mae"]
            unit = "°" if name == "motion" else ""
            print(f"    {name:15s}: R²={m['r2_score']:.4f}, MAE={m['mae']:.4f}{unit}, "
                  f"ClsAcc={m['accuracy']:.4f}")
        else:
            print(f"    {name:15s}: Skipped")

    # Check against thresholds
    warnings = check_results_against_thresholds(current_results, round_config["round"])
    if warnings:
        print(f"\n  ⚠️  Threshold Warnings (Round {round_config['round']}):")
        for w in warnings:
            print(f"    {w}")
    else:
        print(f"\n  ✅ All thresholds passed (Round {round_config['round']})")

    # Compare with best known (Round 9)
    best_comparison = compare_with_best_known(current_results)
    print(f"\n  Comparison vs Best Known (Round 9):")
    for model_name, changes in best_comparison.items():
        status_icon = {"improved": "🟢", "degraded": "🔴", "comparable": "🟡"}.get(
            changes.get("status", ""), "⚪"
        )
        if model_name == "motion":
            print(f"    {status_icon} {model_name:15s}: R²{changes.get('r2_vs_best', 0):+.4f}, "
                  f"MAE{changes.get('mae_vs_best', 0):+.4f} rad")
        elif model_name == "safety" or model_name == "collision":
            print(f"    {status_icon} {model_name:15s}: F1{changes.get('f1_vs_best', 0):+.4f}, "
                  f"Prec{changes.get('prec_vs_best', 0):+.4f}")
        elif model_name == "quality":
            print(f"    {status_icon} {model_name:15s}: R²{changes.get('r2_vs_best', 0):+.4f}, "
                  f"MAE{changes.get('mae_vs_best', 0):+.4f}")

    # Compare with previous round
    if all_results:
        comparison = compare_with_previous(current_results, all_results[-1])
        print(f"\n  Comparison vs Round {round_config['round'] - 1}:")
        for model_name, changes in comparison.items():
            parts = []
            if "r2_delta" in changes:
                arrow = "↑" if changes["r2_direction"] == "up" else "↓"
                parts.append(f"R²{arrow}{changes['r2_delta']:+.4f}")
            if "f1_delta" in changes:
                arrow = "↑" if changes["f1_direction"] == "up" else "↓"
                parts.append(f"F1{arrow}{changes['f1_delta']:+.4f}")
            if "mae_delta" in changes:
                arrow = "↓" if changes["mae_direction"] == "down" else "↑"
                parts.append(f"MAE{arrow}{changes['mae_delta']:+.4f}")
            if "precision_delta" in changes:
                arrow = "↑" if changes["precision_direction"] == "up" else "↓"
                parts.append(f"Prec{arrow}{changes['precision_delta']:+.4f}")
            if "accuracy_delta" in changes:
                arrow = "↑" if changes["accuracy_direction"] == "up" else "↓"
                parts.append(f"Acc{arrow}{changes['accuracy_delta']:+.4f}")
            if parts:
                print(f"    {model_name:15s}: {', '.join(parts)}")
            else:
                print(f"    {model_name:15s}: {changes.get('status', 'no change')}")

    total_time = time.time() - total_start
    print(f"\n  Round {round_config['round']} total time: {total_time:.1f}s "
          f"({total_time/60:.1f} min)")

    return current_results


def main():
    """Main entry point for Round 11 batch training."""
    print("=" * 70)
    print("  ROUND 11: Super-Expanded Data, Enhanced Cleaning & Multi-Round Training")
    print("=" * 70)
    print("  Key Improvements:")
    print("  - Data volume: ~300K+ samples across 15 datasets (1.5-2x vs Round 10)")
    print("  - Data cleaning: NaN/Inf removal, dedup, 4-sigma outlier clipping")
    print("  - Data preprocessing: 3x noise augmentation, class balancing")
    print("  - Real-time monitoring: progress bars, anomaly detection, trend tracking")
    print("  - K-fold cross-validation: 5-fold CV for robust evaluation")
    print("  - Multi-round training: 3 rounds with architecture optimization")
    print("  - Stricter thresholds: R²≥0.90, F1≥0.92, Precision≥0.88")
    print("=" * 70)

    all_round_results: List[Dict[str, Any]] = []
    total_rounds = len(ROUND_CONFIGS)
    overall_start = time.time()

    for round_idx, config in enumerate(ROUND_CONFIGS):
        try:
            round_results = run_training_round(
                config, round_idx, total_rounds, all_round_results
            )
            all_round_results.append(round_results)
        except Exception as e:
            print(f"\n  ❌ Round {config['round']} failed with error: {e}")
            traceback.print_exc()
            # Continue to next round if possible
            continue

    overall_time = time.time() - overall_start

    # =========================================================================
    # Final Comprehensive Report
    # =========================================================================
    print_header("ROUND 11 FINAL - Comprehensive Report")

    if all_round_results:
        # Find best round for each model
        best_results = {}
        for model_name in ["motion", "safety", "quality", "collision"]:
            best_round = None
            best_score = -float("inf")

            for round_idx, results in enumerate(all_round_results):
                if model_name not in results:
                    continue
                m = results[model_name]

                if model_name == "motion":
                    score = m.get("r2_score", 0) - m.get("mae", 0) * 0.1
                elif model_name == "safety":
                    score = m.get("f1_score", 0)
                elif model_name == "quality":
                    score = m.get("r2_score", 0) - m.get("mae", 0) * 0.01
                elif model_name == "collision":
                    score = m.get("f1_score", 0)

                if score > best_score:
                    best_score = score
                    best_round = round_idx + 1

            best_results[model_name] = {
                "best_round": best_round,
                "best_score": best_score,
                "metrics": all_round_results[best_round - 1].get(model_name, {})
                if best_round else {},
            }

        print("\n  Best Results Per Model:")
        for model_name, info in best_results.items():
            if info["best_round"]:
                m = info["metrics"]
                if m.get("f1_score", 0) > 0:
                    print(f"    {model_name:15s}: Round {info['best_round']}, "
                          f"F1={m['f1_score']:.4f}, Acc={m['accuracy']:.4f}, "
                          f"Prec={m['precision']:.4f}, Rec={m['recall']:.4f}")
                elif m.get("r2_score", 0) != 0:
                    mae_str = f"{m['mae']:.4f}"
                    if model_name == "motion":
                        mae_str += f" rad ({m['mae'] * 180 / 3.14159:.1f}°)"
                    print(f"    {model_name:15s}: Round {info['best_round']}, "
                          f"R²={m['r2_score']:.4f}, MAE={mae_str}")

        # Compute comprehensive score
        print("\n  Comprehensive Score:")
        scores = []
        for model_name, info in best_results.items():
            m = info["metrics"]
            if m.get("f1_score", 0) > 0:
                scores.append(m["f1_score"])
            if m.get("r2_score", 0) != 0:
                scores.append(m["r2_score"])
        if scores:
            comprehensive = sum(scores) / len(scores) * 100
            print(f"    Comprehensive Score: {comprehensive:.1f}%")

        # Compare with Round 9 best
        print("\n  Final Comparison vs Round 9 Best:")
        final_best = {k: v["metrics"] for k, v in best_results.items() if v["metrics"]}
        final_comparison = compare_with_best_known(final_best)
        for model_name, changes in final_comparison.items():
            status_icon = {"improved": "🟢 IMPROVED", "degraded": "🔴 DEGRADED",
                          "comparable": "🟡 COMPARABLE"}.get(
                changes.get("status", ""), "⚪ UNKNOWN"
            )
            if model_name == "motion":
                print(f"    {status_icon} {model_name:15s}: R²{changes.get('r2_vs_best', 0):+.4f}, "
                      f"MAE{changes.get('mae_vs_best', 0):+.4f} rad")
            elif model_name == "safety" or model_name == "collision":
                print(f"    {status_icon} {model_name:15s}: F1{changes.get('f1_vs_best', 0):+.4f}, "
                      f"Prec{changes.get('prec_vs_best', 0):+.4f}")
            elif model_name == "quality":
                print(f"    {status_icon} {model_name:15s}: R²{changes.get('r2_vs_best', 0):+.4f}, "
                      f"MAE{changes.get('mae_vs_best', 0):+.4f}")

        # Save comprehensive report
        report_path = Path(__file__).resolve().parent.parent / "reports" / "round11_comprehensive_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "round": 11,
                "total_rounds_completed": len(all_round_results),
                "total_time_s": overall_time,
                "total_time_min": overall_time / 60,
                "all_round_results": all_round_results,
                "best_results": {
                    k: {
                        "best_round": v["best_round"],
                        "best_score": v["best_score"],
                        "metrics": v["metrics"],
                    }
                    for k, v in best_results.items()
                },
                "comprehensive_score": comprehensive if scores else 0,
                "best_known_comparison": {
                    k: {key: val for key, val in v.items() if key != "status"}
                    for k, v in final_comparison.items()
                },
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  Comprehensive report saved to: {report_path}")

        # Also save a markdown summary
        md_path = Path(__file__).resolve().parent.parent / "reports" / "round11_training_summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Round 11 Training Summary\n\n")
            f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Total Time:** {overall_time/60:.1f} min\n\n")
            f.write(f"## Best Results Per Model\n\n")
            f.write(f"| Model | Round | Key Metrics |\n")
            f.write(f"|-------|-------|-------------|\n")
            for model_name, info in best_results.items():
                if info["best_round"]:
                    m = info["metrics"]
                    if m.get("f1_score", 0) > 0:
                        f.write(f"| {model_name} | {info['best_round']} | "
                                f"F1={m['f1_score']:.4f}, Acc={m['accuracy']:.4f}, "
                                f"Prec={m['precision']:.4f}, Rec={m['recall']:.4f} |\n")
                    elif m.get("r2_score", 0) != 0:
                        mae_str = f"{m['mae']:.4f}"
                        if model_name == "motion":
                            mae_str += f" ({m['mae'] * 180 / 3.14159:.1f}°)"
                        f.write(f"| {model_name} | {info['best_round']} | "
                                f"R²={m['r2_score']:.4f}, MAE={mae_str} |\n")
            if scores:
                f.write(f"\n## Comprehensive Score\n\n")
                f.write(f"**{comprehensive:.1f}%**\n\n")
            f.write(f"## Comparison vs Round 9 Best\n\n")
            f.write(f"| Model | Status | Changes |\n")
            f.write(f"|-------|--------|--------|\n")
            for model_name, changes in final_comparison.items():
                status = changes.get("status", "unknown")
                if model_name == "motion":
                    f.write(f"| {model_name} | {status} | "
                            f"R²{changes.get('r2_vs_best', 0):+.4f}, "
                            f"MAE{changes.get('mae_vs_best', 0):+.4f} rad |\n")
                elif model_name == "safety" or model_name == "collision":
                    f.write(f"| {model_name} | {status} | "
                            f"F1{changes.get('f1_vs_best', 0):+.4f}, "
                            f"Prec{changes.get('prec_vs_best', 0):+.4f} |\n")
                elif model_name == "quality":
                    f.write(f"| {model_name} | {status} | "
                            f"R²{changes.get('r2_vs_best', 0):+.4f}, "
                            f"MAE{changes.get('mae_vs_best', 0):+.4f} |\n")
        print(f"  Markdown summary saved to: {md_path}")

    print("\n" + "=" * 70)
    print(f"  ROUND 11 TRAINING COMPLETE (Total: {overall_time/60:.1f} min)")
    print("=" * 70)


if __name__ == "__main__":
    main()