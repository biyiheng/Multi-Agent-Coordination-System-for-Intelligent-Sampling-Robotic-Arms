"""
Automated training Recall monitor / alert gate.

Monitors the collision model's recall after each training run and raises an
alert the moment it drops below a safety threshold (default 0.85). Designed to
be run as a post-training CI gate so a regressed collision model is never
mistakenly accepted.

Round 12 safety requirement: collision recall >= 0.85 AND precision >= 0.20 on
the real (imbalanced) deployment distribution. This script enforces the recall
floor and fails the build with a non-zero exit code when violated.

Usage:
    python -m training.monitor_recall
    python -m training.monitor_recall --threshold 0.85 --model collision
    python -m training.monitor_recall --results reports/model_training_results.json \
        --webhook https://hooks.example.com/alert

Exit codes:
    0  recall >= threshold (PASS)
    1  recall <  threshold (ALERT)
    2  configuration / data error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("monitor_recall")

DEFAULT_THRESHOLD = 0.85
DEFAULT_MODEL = "collision"
DEFAULT_RESULTS = "reports/model_training_results.json"


def load_results(results_path: str) -> Dict[str, Any]:
    """Load the model training results JSON written by ModelTrainer.save_results()."""
    path = Path(results_path)
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_recall(results: Dict[str, Any], model: str) -> Optional[float]:
    """Extract recall for the given model, searching several common keys."""
    model_entry = results.get(model)
    if isinstance(model_entry, dict):
        for key in ("recall", "recall_rate", "sensitivity"):
            val = model_entry.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
    # Fallback: top-level key like "collision_recall"
    for key in (f"{model}_recall", "recall"):
        val = results.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def send_webhook(url: str, payload: Dict[str, Any]) -> bool:
    """Best-effort webhook notification. Returns True on success."""
    if not url:
        return False
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook notification failed: %s", exc)
        return False


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=DEFAULT_RESULTS,
                        help=f"Path to training results JSON (default: {DEFAULT_RESULTS})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to monitor (default: {DEFAULT_MODEL})")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Recall alert threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--webhook", default="",
                        help="Optional webhook URL to POST the alert payload to")
    parser.add_argument("--quiet", action="store_true",
                        help="Only log on alert (no PASS message)")
    args = parser.parse_args(argv)

    try:
        results = load_results(args.results)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load results: %s", exc)
        return 2

    recall = get_recall(results, args.model)
    if recall is None:
        logger.error("Recall not found for model '%s' in %s", args.model, args.results)
        return 2

    passed = recall >= args.threshold
    payload = {
        "event": "recall_alert" if not passed else "recall_ok",
        "model": args.model,
        "recall": round(recall, 4),
        "threshold": args.threshold,
        "passed": passed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "round": "Round 12 safety gate",
    }

    if not passed:
        logger.error(
            "RECALL ALERT: model '%s' recall=%.4f < threshold=%.2f. "
            "Collision model regression detected — DO NOT deploy!",
            args.model, recall, args.threshold,
        )
        send_webhook(args.webhook, payload)
        return 1

    if not args.quiet:
        logger.info("Recall OK: model '%s' recall=%.4f >= threshold=%.2f (PASS)",
                    args.model, recall, args.threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
