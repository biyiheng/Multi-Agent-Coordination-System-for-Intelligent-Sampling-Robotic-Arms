"""Batch training script - Round 9: Precision optimization & stability."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from training.data_generator import DatasetGenerator
from training.model_trainer import ModelTrainer

print("=" * 60)
print("  Round 9: Precision Optimization & Stability")
print("=" * 60)
print("  Targeted improvements:")
print("  - Collision: 7-model ensemble (up from 5), diverse negatives")
print("  - Motion: Fixed seed for reproducible results")
print("  - Safety: Diverse boundary samples for precision")
print("  - Quality: Verified deterministic mapping")
print("=" * 60)

# Regenerate datasets
print("\n[1/2] Regenerating datasets...")
generator = DatasetGenerator()
generator.save_all_datasets()

# Train all models
print("\n[2/2] Training ML models...")
trainer = ModelTrainer()
trainer.train_all()

# Save results
trainer.save_results()

# Print final summary
print("\n" + "=" * 60)
print("  ROUND 9 FINAL - Complete Results")
print("=" * 60)
for name, metrics in trainer.results.items():
    if metrics.f1_score > 0:
        print(f"  {name:15s}: F1={metrics.f1_score:.4f}, Acc={metrics.accuracy:.4f}, "
              f"Prec={metrics.precision:.4f}, Rec={metrics.recall:.4f}")
    elif metrics.r2_score != 0:
        print(f"  {name:15s}: R²={metrics.r2_score:.4f}, MAE={metrics.mae:.4f}, "
              f"ClsAcc={metrics.accuracy:.4f}")
    else:
        print(f"  {name:15s}: Skipped")
print("=" * 60)