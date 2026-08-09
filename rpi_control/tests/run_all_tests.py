#!/usr/bin/env python3
"""
Comprehensive test runner for the intelligent sampling robotic arm system.

Runs all test suites (black-box, white-box, performance, security) and
generates a JSON report with results and recommendations.

Usage:
    python run_all_tests.py                  # Run all tests
    python run_all_tests.py --quick           # Skip performance tests
    python run_all_tests.py --report report.json  # Custom report path
    python run_all_tests.py --verbose         # Show detailed output
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# Configuration
# =============================================================================

TESTS_DIR = Path(__file__).resolve().parent
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TEST_SUITES = {
    "blackbox": {
        "file": "test_blackbox_api.py",
        "description": "Black-box API endpoint tests",
        "category": "functional",
        "marker": "BlackBox",
    },
    "whitebox": {
        "file": "test_whitebox_core.py",
        "description": "White-box core logic tests",
        "category": "functional",
        "marker": "WhiteBox",
    },
    "performance": {
        "file": "test_performance.py",
        "description": "Performance and memory benchmarks",
        "category": "performance",
        "marker": "Performance",
    },
    "security": {
        "file": "test_security.py",
        "description": "Security analysis and vulnerability scan",
        "category": "security",
        "marker": "Security",
    },
}


# =============================================================================
# Test Runner
# =============================================================================

def run_test_suite(
    suite_name: str,
    suite_config: Dict[str, str],
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run a single test suite and return results.

    Args:
        suite_name: Name of the test suite.
        suite_config: Configuration dict with 'file' and other keys.
        verbose: Whether to show detailed output.

    Returns:
        Dict with test results.
    """
    test_file = TESTS_DIR / suite_config["file"]
    if not test_file.exists():
        return {
            "suite": suite_name,
            "status": "skipped",
            "reason": f"Test file not found: {test_file}",
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration_seconds": 0,
        }

    print(f"\n{'=' * 60}")
    print(f"  Running: {suite_config['description']}")
    print(f"  File: {suite_config['file']}")
    print(f"{'=' * 60}")

    start_time = time.perf_counter()

    try:
        # Run pytest with JSON output
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v" if verbose else "-q",
                "--tb=short",
                "--no-header",
                f"--rootdir={TESTS_DIR.parent}",
            ],
            cwd=str(TESTS_DIR.parent),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per suite
        )

        elapsed = time.perf_counter() - start_time

        # Parse pytest output
        stdout = result.stdout
        stderr = result.stderr

        # Count test results from output
        passed = stdout.count("PASSED") + stdout.count(".")
        failed = stdout.count("FAILED") + stdout.count("F")
        errors = stdout.count("ERRORS") + stdout.count("E")
        skipped = stdout.count("SKIPPED") + stdout.count("s")

        # More accurate parsing from pytest summary line
        summary_match = None
        for line in stdout.split("\n"):
            if "passed" in line or "failed" in line:
                summary_match = line
                break

        if summary_match:
            import re
            passed_match = re.search(r'(\d+)\s+passed', summary_match)
            failed_match = re.search(r'(\d+)\s+failed', summary_match)
            error_match = re.search(r'(\d+)\s+error', summary_match)

            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            errors = int(error_match.group(1)) if error_match else 0

        total = passed + failed + errors

        status = "passed" if failed == 0 and errors == 0 else "failed"

        if verbose:
            print(stdout)
            if stderr:
                print(f"STDERR:\n{stderr}")

        return {
            "suite": suite_name,
            "description": suite_config["description"],
            "category": suite_config["category"],
            "status": status,
            "tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "duration_seconds": round(elapsed, 2),
            "output_summary": summary_match or "",
        }

    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start_time
        return {
            "suite": suite_name,
            "status": "timeout",
            "reason": "Test suite timed out after 300s",
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration_seconds": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return {
            "suite": suite_name,
            "status": "error",
            "reason": str(e),
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration_seconds": round(elapsed, 2),
        }


def run_all_tests(
    suites: Optional[List[str]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run all configured test suites.

    Args:
        suites: Optional list of suite names to run. If None, runs all.
        verbose: Whether to show detailed output.

    Returns:
        Comprehensive test report dict.
    """
    if suites is None:
        suites = list(TEST_SUITES.keys())

    print("=" * 70)
    print("  INTELLIGENT SAMPLING ROBOTIC ARM - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print(f"  Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version}")
    print(f"  Test directory: {TESTS_DIR}")
    print(f"  Suites to run: {', '.join(suites)}")
    print("=" * 70)

    total_start = time.perf_counter()

    results = []
    for suite_name in suites:
        if suite_name not in TEST_SUITES:
            print(f"WARNING: Unknown test suite '{suite_name}', skipping")
            continue

        result = run_test_suite(suite_name, TEST_SUITES[suite_name], verbose)
        results.append(result)

        # Print quick status
        emoji = "✓" if result["status"] == "passed" else "✗"
        print(f"\n  {emoji} {suite_name}: {result['status']} "
              f"({result['passed']}/{result['tests']} passed) "
              f"in {result['duration_seconds']:.1f}s")

    total_elapsed = time.perf_counter() - total_start

    # Calculate summary
    total_tests = sum(r["tests"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    all_passed = all(r["status"] == "passed" for r in results
                     if r["status"] not in ("skipped",))

    report = {
        "report_type": "comprehensive_test_report",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round(total_elapsed, 2),
        "summary": {
            "total_suites": len(results),
            "passed_suites": sum(1 for r in results if r["status"] == "passed"),
            "failed_suites": sum(1 for r in results if r["status"] == "failed"),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "pass_rate": round(total_passed / max(total_tests, 1) * 100, 1),
            "overall_status": "PASSED" if all_passed else "FAILED",
        },
        "suites": results,
        "recommendations": generate_recommendations(results),
    }

    return report


def generate_recommendations(results: List[Dict[str, Any]]) -> List[str]:
    """Generate recommendations based on test results.

    Args:
        results: List of test suite results.

    Returns:
        List of recommendation strings.
    """
    recommendations = []

    for r in results:
        if r["status"] == "failed":
            recommendations.append(
                f"[{r['suite']}] {r['failed']} tests failed in {r['description']}. "
                f"Review test output for details."
            )
        elif r["status"] == "timeout":
            recommendations.append(
                f"[{r['suite']}] {r['description']} timed out. "
                f"Consider optimizing slow operations or increasing timeout."
            )
        elif r["status"] == "error":
            recommendations.append(
                f"[{r['suite']}] {r['description']} encountered an error: "
                f"{r.get('reason', 'unknown')}"
            )

    # Performance-specific recommendations
    for r in results:
        if r["suite"] == "performance" and r["status"] == "failed":
            recommendations.append(
                "Performance benchmarks failed. Review slow operations "
                "and consider algorithmic optimization or caching."
            )

    # Security-specific recommendations
    for r in results:
        if r["suite"] == "security":
            recommendations.append(
                "Review security warnings above. Prioritize: "
                "1) Add API authentication, 2) Restrict CORS, "
                "3) Add input validation with Pydantic models."
            )

    if not recommendations:
        recommendations.append("All test suites passed. No critical issues found.")

    return recommendations


# =============================================================================
# Report Generation
# =============================================================================

def save_report(report: Dict[str, Any], report_path: Path) -> None:
    """Save the test report to a JSON file.

    Args:
        report: Test report dict.
        report_path: Path to save the report.
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report saved to: {report_path}")


def print_summary(report: Dict[str, Any]) -> None:
    """Print a formatted test summary.

    Args:
        report: Test report dict.
    """
    summary = report["summary"]
    print(f"\n{'=' * 70}")
    print(f"  TEST SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Overall Status:  {summary['overall_status']}")
    print(f"  Pass Rate:       {summary['pass_rate']}%")
    print(f"  Total Tests:     {summary['total_tests']}")
    print(f"  Passed:          {summary['total_passed']}")
    print(f"  Failed:          {summary['total_failed']}")
    print(f"  Errors:          {summary['total_errors']}")
    print(f"  Duration:        {report['duration_seconds']:.1f}s")
    print(f"{'=' * 70}")

    # Per-suite breakdown
    print(f"\n  Suite Breakdown:")
    for r in report["suites"]:
        status_icon = "✓" if r["status"] == "passed" else "✗"
        if r["status"] == "skipped":
            status_icon = "○"
        print(f"    {status_icon} {r['suite']:15s} {r['status']:8s}  "
              f"{r['passed']:3d}/{r['tests']:3d} passed  "
              f"{r['duration_seconds']:6.1f}s")

    # Recommendations
    if report["recommendations"]:
        print(f"\n  Recommendations:")
        for rec in report["recommendations"]:
            print(f"    • {rec}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for the robotic arm system"
    )
    parser.add_argument(
        "--suites",
        nargs="+",
        choices=list(TEST_SUITES.keys()),
        default=None,
        help="Specific test suites to run (default: all)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip performance tests (faster)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Custom report file path (default: reports/test_report_TIMESTAMP.json)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed test output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON to stdout",
    )

    args = parser.parse_args()

    # Determine suites
    suites = args.suites
    if suites is None:
        suites = list(TEST_SUITES.keys())
        if args.quick:
            suites = [s for s in suites if s != "performance"]

    # Run tests
    report = run_all_tests(suites, verbose=args.verbose)

    # Save report
    if args.report:
        report_path = Path(args.report)
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"test_report_{timestamp}.json"

    save_report(report, report_path)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_summary(report)

    # Exit with appropriate code
    if report["summary"]["overall_status"] == "FAILED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()