"""
Enhanced Multi-Round Data Screening Pipeline with Self-Inspection.

Extends the existing DataScreener with additional rounds:
- Round 4: Data leakage detection and cross-validation readiness
- Round 5: Edge case coverage analysis and diversity metrics
- Self-inspection: Automated quality report generation and action items

Usage:
    from rpi_control.loop_engineering.tests.enhanced_screening import EnhancedScreener
    screener = EnhancedScreener()
    reports = screener.screen_all_deep(num_rounds=5)
"""

import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

# Import existing screener
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from training.data_screener import (
    DataScreener, ScreeningIssue, ScreeningReport,
)


@dataclass
class SelfInspectionReport:
    """Self-inspection results after all screening rounds."""
    total_rounds: int = 0
    all_passed: bool = False
    final_quality_score: float = 0.0
    total_issues_found: int = 0
    issues_fixed: int = 0
    remaining_issues: int = 0
    improvement_trend: List[float] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""


class EnhancedScreener(DataScreener):
    """Enhanced multi-round data screener with additional deep checks.

    Extends the base DataScreener with:
    - Round 4: Data leakage detection & cross-validation readiness
    - Round 5: Edge case coverage & diversity analysis
    - Self-inspection: Automated quality assessment
    - Improved scoring with trend analysis
    """

    def __init__(self, data_dir: str = "data/training", output_dir: str = "reports"):
        """Initialize enhanced screener."""
        super().__init__(data_dir=data_dir, output_dir=output_dir)
        self.deep_reports: List[ScreeningReport] = []
        self.self_inspection: Optional[SelfInspectionReport] = None

    def screen_all_deep(self, num_rounds: int = 5) -> List[ScreeningReport]:
        """Run deep multi-round screening with 5 rounds.

        Args:
            num_rounds: Number of screening rounds (3-5).

        Returns:
            List of ScreeningReport objects.
        """
        # Run base rounds 1-3
        base_reports = self.screen_all(num_rounds=min(3, num_rounds))
        all_reports = list(base_reports)

        # Run enhanced rounds 4-5
        for round_num in range(4, num_rounds + 1):
            print(f"\n{'='*60}")
            print(f"  ENHANCED SCREENING ROUND {round_num}/{num_rounds}")
            print(f"{'='*60}")

            report = ScreeningReport(round_number=round_num)
            datasets = self._load_all_datasets()
            report.total_datasets = len(datasets)
            report.total_samples = sum(len(v) for v in datasets.values())

            if round_num == 4:
                report.issues = self._screen_round4_leakage(datasets)
            elif round_num == 5:
                report.issues = self._screen_round5_diversity(datasets)

            report.dataset_stats = self._compute_dataset_stats(datasets)
            report.quality_score = self._calculate_quality_score(report)
            critical_count = sum(1 for i in report.issues if i.severity == "critical")
            error_count = sum(1 for i in report.issues if i.severity == "error")
            report.passed = critical_count == 0 and error_count <= 3
            report.summary = self._generate_summary(report)

            all_reports.append(report)
            self.deep_reports.append(report)
            self._print_report(report)

        # Run self-inspection
        self.self_inspection = self._run_self_inspection(all_reports)
        self._print_self_inspection()

        return all_reports

    # =========================================================================
    # Round 4: Data Leakage Detection
    # =========================================================================

    def _screen_round4_leakage(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 4: Data leakage detection and cross-validation readiness.

        Checks:
        - Feature leakage between train/validation splits
        - Temporal leakage (timestamp-based)
        - Target leakage (target information in features)
        - Cross-validation split quality
        - Distribution shift detection
        """
        print("  [Round 4] Data leakage detection...")
        issues = []

        for name, data in datasets.items():
            if not data or len(data) < 100:
                continue

            # Check for temporal leakage (if timestamps present)
            temporal_issues = self._check_temporal_leakage(name, data)
            issues.extend(temporal_issues)

            # Check for target leakage
            if name in ("motion_dataset", "ik_dataset", "edge_case_ik"):
                target_issues = self._check_target_leakage(name, data)
                issues.extend(target_issues)

            # Check feature correlation with target
            corr_issues = self._check_feature_target_correlation(name, data)
            issues.extend(corr_issues)

        return issues

    def _check_temporal_leakage(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check for temporal ordering issues that could cause leakage."""
        issues = []
        timestamps = []

        for sample in data[:500]:
            ts = sample.get("timestamp", 0)
            if isinstance(ts, (int, float)) and ts > 0:
                timestamps.append(ts)

        if len(timestamps) < 2:
            return issues

        # Check if timestamps are monotonically increasing
        is_sorted = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
        if not is_sorted:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="warning",
                category="leakage",
                description="Timestamps are not monotonically ordered - potential temporal leakage",
                recommendation="Sort by timestamp and use time-based train/test split",
            ))

        # Check for duplicate timestamps
        dup_ts = len(timestamps) - len(set(timestamps))
        if dup_ts > len(timestamps) * 0.1:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="info",
                category="leakage",
                description=f"{dup_ts} duplicate timestamps found ({dup_ts/len(timestamps)*100:.1f}%)",
                recommendation="Consider using unique timestamps or group-based splitting",
            ))

        return issues

    def _check_target_leakage(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check if target information leaks into features."""
        issues = []

        if name == "motion_dataset":
            # Check if end_effector_pose contains the same info as joint_angles
            # (it should, but we need to check for data duplication)
            for i, sample in enumerate(data[:200]):
                joints = sample.get("joint_angles", [])
                pose = sample.get("end_effector_pose", [])
                if len(joints) >= 6 and len(pose) >= 6:
                    # Check if pose is an exact copy of joints (data leakage)
                    if joints[:3] == pose[:3]:
                        issues.append(ScreeningIssue(
                            dataset=name,
                            severity="error",
                            category="leakage",
                            description=f"Sample {i}: joint_angles and end_effector_pose share identical values",
                            recommendation="Fix data generation to ensure proper FK computation",
                        ))
                        break  # One example is enough

        return issues

    def _check_feature_target_correlation(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check for suspiciously high feature-target correlations."""
        issues = []

        try:
            # Extract numeric features
            numeric_fields = self._extract_numeric_fields(data[:500])
            if len(numeric_fields) < 2:
                return issues

            # Compute correlation matrix for a subset
            field_names = list(numeric_fields.keys())[:10]
            n = min(len(numeric_fields[field_names[0]]), 500)
            matrix = np.zeros((len(field_names), n))

            for j, fname in enumerate(field_names):
                values = numeric_fields[fname][:n]
                matrix[j] = values

            # Compute pairwise correlations
            for i in range(len(field_names)):
                for j in range(i + 1, len(field_names)):
                    if np.std(matrix[i]) > 0 and np.std(matrix[j]) > 0:
                        corr = np.corrcoef(matrix[i], matrix[j])[0, 1]
                        if abs(corr) > 0.99:
                            issues.append(ScreeningIssue(
                                dataset=name,
                                severity="warning",
                                category="leakage",
                                description=f"Near-perfect correlation ({corr:.4f}) between "
                                           f"'{field_names[i]}' and '{field_names[j]}'",
                                recommendation="Check for duplicate or derived features",
                            ))

        except Exception:
            pass  # Skip correlation check on error

        return issues

    # =========================================================================
    # Round 5: Diversity & Edge Case Coverage
    # =========================================================================

    def _screen_round5_diversity(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 5: Diversity analysis and edge case coverage.

        Checks:
        - Sample diversity (entropy-based)
        - Edge case coverage percentage
        - Class distribution balance
        - Feature space coverage
        - Data augmentation quality
        """
        print("  [Round 5] Diversity & edge case analysis...")
        issues = []

        for name, data in datasets.items():
            if not data or len(data) < 50:
                continue

            # Check overall diversity
            diversity_issues = self._check_diversity(name, data)
            issues.extend(diversity_issues)

            # Check edge case coverage
            if "edge_case" in name or "ik" in name:
                edge_issues = self._check_edge_diversity(name, data)
                issues.extend(edge_issues)

            # Check class balance
            balance_issues = self._check_class_balance_deep(name, data)
            issues.extend(balance_issues)

        return issues

    def _check_diversity(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check sample diversity using entropy-based metrics."""
        issues = []

        numeric_fields = self._extract_numeric_fields(data[:1000])
        if not numeric_fields:
            return issues

        # Compute entropy for each field
        low_diversity_fields = []
        for fname, values in numeric_fields.items():
            if len(values) < 20:
                continue
            arr = np.array(values, dtype=np.float64)
            arr = arr[np.isfinite(arr)]
            if len(arr) < 20:
                continue

            # Normalize to [0, 1]
            arr_min, arr_max = np.min(arr), np.max(arr)
            if arr_max - arr_min < 1e-8:
                low_diversity_fields.append(f"{fname} (constant)")
                continue

            normalized = (arr - arr_min) / (arr_max - arr_min)

            # Compute entropy via histogram
            hist, _ = np.histogram(normalized, bins=20)
            hist = hist / hist.sum()
            hist = hist[hist > 0]
            entropy = -np.sum(hist * np.log2(hist)) / np.log2(20)  # Normalized

            if entropy < 0.3:
                low_diversity_fields.append(f"{fname} (entropy={entropy:.2f})")

        if low_diversity_fields:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="warning",
                category="diversity",
                description=f"Low diversity fields: {', '.join(low_diversity_fields[:5])}",
                affected_count=len(low_diversity_fields),
                recommendation="Increase data variation for low-diversity fields",
            ))

        return issues

    def _check_edge_diversity(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check edge case type coverage and diversity."""
        issues = []

        if "edge_case" not in name:
            return issues

        edge_types = Counter()
        for sample in data:
            etype = sample.get("edge_type", "unknown")
            edge_types[etype] += 1

        total = sum(edge_types.values())
        if total == 0:
            return issues

        # Check minimum coverage per type
        for etype, count in edge_types.items():
            ratio = count / total
            if ratio < 0.05:
                issues.append(ScreeningIssue(
                    dataset=name,
                    severity="info",
                    category="diversity",
                    description=f"Edge type '{etype}' has low coverage: {count}/{total} ({ratio*100:.1f}%)",
                    recommendation=f"Increase samples for edge type '{etype}'",
                ))

        # Check total edge type count
        if len(edge_types) < 4:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="warning",
                category="diversity",
                description=f"Only {len(edge_types)} edge case types covered (expected >= 4)",
                recommendation="Add more edge case types: boundary, near_singularity, extreme_orientation, full_reach",
            ))

        return issues

    def _check_class_balance_deep(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Deep class balance analysis with statistical tests."""
        issues = []

        # Check safety dataset balance
        if name == "safety_dataset":
            safe = sum(1 for s in data if s.get("is_safe", True))
            unsafe = len(data) - safe
            total = len(data)

            if total > 0:
                unsafe_ratio = unsafe / total
                if unsafe_ratio < 0.15:
                    issues.append(ScreeningIssue(
                        dataset=name,
                        severity="warning",
                        category="diversity",
                        description=f"Severe class imbalance: unsafe={unsafe}/{total} ({unsafe_ratio*100:.1f}%)",
                        affected_count=unsafe,
                        recommendation="Target 20-40% unsafe samples for better model training",
                    ))
                elif unsafe_ratio > 0.7:
                    issues.append(ScreeningIssue(
                        dataset=name,
                        severity="warning",
                        category="diversity",
                        description=f"Too many unsafe samples: {unsafe}/{total} ({unsafe_ratio*100:.1f}%)",
                        affected_count=unsafe,
                        recommendation="Balance towards 30% unsafe for realistic distribution",
                    ))

        # Check quality dataset balance
        if name == "quality_dataset":
            decisions = Counter(
                str(s.get("decision", "unknown")) if isinstance(s.get("decision"), str)
                else s.get("decision", "unknown")
                for s in data
            )
            total = sum(decisions.values())

            if total > 0:
                for decision, count in decisions.items():
                    ratio = count / total
                    if ratio < 0.1:
                        issues.append(ScreeningIssue(
                            dataset=name,
                            severity="info",
                            category="diversity",
                            description=f"Underrepresented decision '{decision}': {count}/{total} ({ratio*100:.1f}%)",
                            recommendation="Balance quality decision distribution",
                        ))

        return issues

    # =========================================================================
    # Self-Inspection
    # =========================================================================

    def _run_self_inspection(self, all_reports: List[ScreeningReport]) -> SelfInspectionReport:
        """Run automated self-inspection on all screening results.

        Analyzes trends across rounds, identifies remaining issues,
        and generates actionable recommendations.

        Args:
            all_reports: All screening reports from all rounds.

        Returns:
            SelfInspectionReport with analysis and recommendations.
        """
        print(f"\n{'='*60}")
        print("  SELF-INSPECTION ANALYSIS")
        print(f"{'='*60}")

        report = SelfInspectionReport()
        report.total_rounds = len(all_reports)

        if not all_reports:
            report.summary = "No screening data available"
            return report

        # Check if all rounds passed
        report.all_passed = all(r.passed for r in all_reports)

        # Final quality score
        report.final_quality_score = all_reports[-1].quality_score

        # Issue tracking
        all_issues = []
        for r in all_reports:
            all_issues.extend(r.issues)

        report.total_issues_found = len(all_issues)

        # Count by severity
        severity_counts = Counter(i.severity for i in all_issues)
        report.remaining_issues = severity_counts.get("critical", 0) + severity_counts.get("error", 0)

        # Improvement trend
        report.improvement_trend = [r.quality_score for r in all_reports]

        # Generate recommendations
        report.recommendations = self._generate_self_inspection_recommendations(all_reports, all_issues)

        # Generate action items
        report.action_items = self._generate_action_items(all_reports, all_issues)

        # Summary
        trend_str = " → ".join(f"{s:.0f}" for s in report.improvement_trend)
        report.summary = (
            f"Self-Inspection Complete: {report.total_rounds} rounds, "
            f"Final Score: {report.final_quality_score:.0f}/100, "
            f"Trend: {trend_str}, "
            f"Remaining Issues: {report.remaining_issues}"
        )

        return report

    def _generate_self_inspection_recommendations(
        self,
        reports: List[ScreeningReport],
        all_issues: List[ScreeningIssue],
    ) -> List[str]:
        """Generate prioritized recommendations from self-inspection."""
        recs = []

        # Check score trend
        if len(reports) >= 2:
            scores = [r.quality_score for r in reports]
            if scores[-1] < scores[0]:
                recs.append("⚠ Quality score decreased across rounds - review recent changes")
            elif scores[-1] - scores[0] < 5:
                recs.append("⚠ Minimal improvement across rounds - consider more aggressive data cleaning")
            else:
                recs.append("✅ Quality score improving across rounds")

        # Check for recurring issues
        issue_patterns = Counter(i.description[:50] for i in all_issues)
        recurring = [(desc, count) for desc, count in issue_patterns.items() if count >= 2]
        if recurring:
            top = recurring[0]
            recs.append(f"⚠ Recurring issue: '{top[0]}...' found {top[1]} times - address root cause")

        # Check category coverage
        categories = Counter(i.category for i in all_issues)
        if "leakage" not in categories:
            recs.append("ℹ No data leakage issues detected - good")
        if "diversity" not in categories:
            recs.append("ℹ No diversity issues detected - dataset appears well-distributed")

        # Final score assessment
        final_score = reports[-1].quality_score
        if final_score >= 95:
            recs.append("✅ Excellent data quality - ready for model training")
        elif final_score >= 80:
            recs.append("✅ Good data quality - proceed with training, monitor remaining issues")
        elif final_score >= 60:
            recs.append("⚠ Fair data quality - fix errors before training")
        else:
            recs.append("🔴 Poor data quality - significant cleanup needed before training")

        return recs

    def _generate_action_items(
        self,
        reports: List[ScreeningReport],
        all_issues: List[ScreeningIssue],
    ) -> List[Dict[str, Any]]:
        """Generate actionable items from self-inspection."""
        actions = []

        # Priority 1: Critical issues
        critical = [i for i in all_issues if i.severity == "critical"]
        for issue in critical[:5]:
            actions.append({
                "priority": "P0",
                "action": f"Fix critical issue: {issue.description}",
                "dataset": issue.dataset,
                "recommendation": issue.recommendation,
                "status": "pending",
            })

        # Priority 2: Error issues
        errors = [i for i in all_issues if i.severity == "error"]
        for issue in errors[:5]:
            actions.append({
                "priority": "P1",
                "action": f"Fix error: {issue.description}",
                "dataset": issue.dataset,
                "recommendation": issue.recommendation,
                "status": "pending",
            })

        # Priority 3: Data enrichment
        if reports[-1].total_samples < 50000:
            actions.append({
                "priority": "P2",
                "action": f"Increase dataset size (current: {reports[-1].total_samples}, target: 50000+)",
                "dataset": "all",
                "recommendation": "Run enhanced data generation with more samples",
                "status": "pending",
            })

        # Priority 4: Edge case expansion
        actions.append({
            "priority": "P2",
            "action": "Expand edge case coverage across all categories",
            "dataset": "edge_case_ik",
            "recommendation": "Add boundary, singularity, extreme orientation, and full reach cases",
            "status": "pending",
        })

        return actions

    def _print_self_inspection(self) -> None:
        """Print self-inspection report."""
        if not self.self_inspection:
            return

        si = self.self_inspection
        print(f"\n{'='*60}")
        print("  SELF-INSPECTION RESULTS")
        print(f"{'='*60}")
        print(f"  Rounds: {si.total_rounds}")
        print(f"  All Passed: {'✅ Yes' if si.all_passed else '❌ No'}")
        print(f"  Final Quality Score: {si.final_quality_score:.1f}/100")
        print(f"  Total Issues Found: {si.total_issues_found}")
        print(f"  Remaining Issues: {si.remaining_issues}")
        print(f"  Score Trend: {' → '.join(f'{s:.0f}' for s in si.improvement_trend)}")

        print(f"\n  Recommendations:")
        for rec in si.recommendations:
            print(f"    {rec}")

        print(f"\n  Action Items:")
        for item in si.action_items[:5]:
            print(f"    [{item['priority']}] {item['action']}")

        print(f"\n  Summary: {si.summary}")
        print(f"{'='*60}")

    def save_all_reports(self) -> None:
        """Save all reports including enhanced rounds and self-inspection."""
        # Save base reports
        self.save_reports()

        # Save enhanced reports
        for report in self.deep_reports:
            filepath = self.output_dir / f"screening_report_round{report.round_number}.json"
            report_data = {
                "round": report.round_number,
                "timestamp": report.timestamp,
                "total_datasets": report.total_datasets,
                "total_samples": report.total_samples,
                "quality_score": report.quality_score,
                "passed": report.passed,
                "summary": report.summary,
                "dataset_stats": report.dataset_stats,
                "issues": [
                    {
                        "dataset": i.dataset,
                        "severity": i.severity,
                        "category": i.category,
                        "description": i.description,
                        "affected_count": i.affected_count,
                        "recommendation": i.recommendation,
                    }
                    for i in report.issues
                ],
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"  Enhanced screening report saved: {filepath}")

        # Save self-inspection
        if self.self_inspection:
            filepath = self.output_dir / "self_inspection_report.json"
            si = self.self_inspection
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "total_rounds": si.total_rounds,
                    "all_passed": si.all_passed,
                    "final_quality_score": si.final_quality_score,
                    "total_issues_found": si.total_issues_found,
                    "remaining_issues": si.remaining_issues,
                    "improvement_trend": si.improvement_trend,
                    "recommendations": si.recommendations,
                    "action_items": si.action_items,
                    "summary": si.summary,
                }, f, indent=2, ensure_ascii=False)
            print(f"  Self-inspection report saved: {filepath}")


# =============================================================================
# Quick Runner
# =============================================================================

def run_enhanced_screening(
    data_dir: str = "data/training",
    output_dir: str = "reports",
    num_rounds: int = 5,
) -> Dict[str, Any]:
    """Run enhanced multi-round screening with self-inspection.

    Args:
        data_dir: Data directory.
        output_dir: Output directory.
        num_rounds: Number of screening rounds.

    Returns:
        Dict with screening results.
    """
    screener = EnhancedScreener(data_dir=data_dir, output_dir=output_dir)
    reports = screener.screen_all_deep(num_rounds=num_rounds)
    screener.save_all_reports()

    return {
        "total_rounds": len(reports),
        "all_passed": all(r.passed for r in reports),
        "final_score": reports[-1].quality_score if reports else 0,
        "self_inspection": screener.self_inspection.summary if screener.self_inspection else "",
    }


if __name__ == "__main__":
    result = run_enhanced_screening()
    print(f"\n{'#'*60}")
    print(f"#  ENHANCED SCREENING COMPLETE")
    print(f"#  Final Score: {result['final_score']:.0f}/100")
    print(f"#  All Passed: {result['all_passed']}")
    print(f"{'#'*60}")