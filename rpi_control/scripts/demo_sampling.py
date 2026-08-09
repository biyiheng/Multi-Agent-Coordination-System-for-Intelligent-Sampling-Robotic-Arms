#!/usr/bin/env python3
"""Demo sampling task for the intelligent sampling robotic arm.

This script runs a complete demo sampling cycle:
1. Plan a grid of sampling points
2. Move the arm to each point
3. Simulate sample collection
4. Generate a summary report
"""

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class DemoSamplingTask:
    """Runs a complete demo sampling cycle."""

    def __init__(self, bounds: Dict[str, float], step: float = 50.0):
        self.bounds = bounds
        self.step = step
        self.samples: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None

    def plan_points(self) -> List[Dict[str, float]]:
        """Generate grid sampling points within bounds."""
        points = []
        x = self.bounds["x_min"]
        while x <= self.bounds["x_max"]:
            y = self.bounds["y_min"]
            while y <= self.bounds["y_max"]:
                points.append({"x": x, "y": y, "z": self.bounds.get("z", 10.0)})
                y += self.step
            x += self.step
        return points

    def simulate_sample(self, position: Dict[str, float]) -> Dict[str, Any]:
        """Simulate collecting a sample at the given position."""
        import random

        # Simulate quality score with some variation
        quality = round(random.uniform(0.75, 0.99), 3)

        # Simulate possible defects
        defects = []
        if random.random() < 0.1:
            defects.append("surface_scratch")
        if random.random() < 0.05:
            defects.append("color_anomaly")

        return {
            "position": position,
            "quality_score": quality,
            "defects": defects,
            "dimensions": {
                "width": round(random.uniform(10, 30), 1),
                "height": round(random.uniform(5, 15), 1),
            },
            "passed": quality >= 0.8,
            "timestamp": datetime.now().isoformat(),
        }

    def print_progress(self, current, total, position):
        """Print progress bar."""
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = "=" * filled + "-" * (bar_length - filled)
        percent = current / total * 100
        print(f"\r[{bar}] {percent:.1f}% ({current}/{total}) "
              f"at ({position['x']:.0f}, {position['y']:.0f})", end="")

    def run(self):
        """Execute the demo sampling task."""
        print("=" * 60)
        print("  Intelligent Sampling Demo")
        print("=" * 60)
        print()
        print(f"Bounds: X[{self.bounds['x_min']}, {self.bounds['x_max']}], "
              f"Y[{self.bounds['y_min']}, {self.bounds['y_max']}], "
              f"Z={self.bounds.get('z', 10)}")
        print(f"Strategy: grid, Step: {self.step}mm")
        print()

        # Plan points
        points = self.plan_points()
        total = len(points)
        print(f"Planned {total} sampling points")
        print()

        # Start sampling
        self.start_time = time.time()
        print("Starting sampling...")
        print()

        for i, point in enumerate(points, 1):
            # Simulate arm movement
            print(f"  Moving to ({point['x']:.0f}, {point['y']:.0f}, {point['z']:.0f})...", end=" ")
            time.sleep(0.3)  # Simulated movement time
            print("Done")

            # Simulate sample collection
            print(f"  Collecting sample...", end=" ")
            sample = self.simulate_sample(point)
            sample["id"] = f"SAMPLE-{i:04d}"
            self.samples.append(sample)
            print(f"Quality: {sample['quality_score']:.3f} "
                  f"({'PASS' if sample['passed'] else 'FAIL'})")

            self.print_progress(i, total, point)
            print()

        self.end_time = time.time()

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate and print a summary report."""
        elapsed = self.end_time - self.start_time
        total = len(self.samples)
        passed = sum(1 for s in self.samples if s["passed"])
        failed = total - passed
        avg_quality = sum(s["quality_score"] for s in self.samples) / total if total > 0 else 0
        defects_found = sum(len(s["defects"]) for s in self.samples)

        print()
        print("=" * 60)
        print("  SAMPLING REPORT")
        print("=" * 60)
        print()
        print(f"  Task Duration:       {elapsed:.1f}s")
        print(f"  Total Samples:       {total}")
        print(f"  Passed:              {passed} ({passed/total*100:.1f}%)" if total > 0 else "  Passed: 0")
        print(f"  Failed:              {failed} ({failed/total*100:.1f}%)" if total > 0 else "  Failed: 0")
        print(f"  Average Quality:     {avg_quality:.3f}")
        print(f"  Defects Detected:    {defects_found}")
        print(f"  Avg Time per Sample: {elapsed/total:.1f}s" if total > 0 else "  N/A")
        print()

        # Save report
        report_dir = Path("./data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"demo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            "timestamp": datetime.now().isoformat(),
            "bounds": self.bounds,
            "step": self.step,
            "strategy": "grid",
            "duration_seconds": elapsed,
            "total_samples": total,
            "passed": passed,
            "failed": failed,
            "average_quality": avg_quality,
            "total_defects": defects_found,
            "samples": self.samples,
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"  Report saved to: {report_path}")
        print()


def main():
    """Main entry point for demo."""
    # Default bounds for demo
    bounds = {
        "x_min": 0.0,
        "x_max": 100.0,
        "y_min": 0.0,
        "y_max": 100.0,
        "z": 10.0,
    }

    step = 50.0

    print("\nDemo Sampling Configuration")
    print("-" * 30)
    print(f"X range: [{bounds['x_min']}, {bounds['x_max']}]")
    print(f"Y range: [{bounds['y_min']}, {bounds['y_max']}]")
    print(f"Z height: {bounds['z']}")
    print(f"Grid step: {step}mm")

    x_points = int((bounds["x_max"] - bounds["x_min"]) / step) + 1
    y_points = int((bounds["y_max"] - bounds["y_min"]) / step) + 1
    total = x_points * y_points
    print(f"Total points: {x_points}x{y_points} = {total}")
    print()

    confirm = input("Start demo? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("Demo cancelled.")
        return

    task = DemoSamplingTask(bounds, step)
    task.run()


if __name__ == "__main__":
    main()