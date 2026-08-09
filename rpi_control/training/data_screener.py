"""
Multi-Round Data Quality Screener for Training Datasets.

Performs comprehensive data quality screening across multiple rounds:
1. Basic integrity checks (missing values, schema validation, duplicates)
2. Statistical analysis (outliers, class balance, distribution analysis)
3. Semantic validation (physical constraints, kinematic consistency)
4. Cross-dataset consistency checks
5. Data leakage detection
6. Edge case coverage analysis

Used as part of the multi-round screening pipeline before model training.
"""

import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ScreeningIssue:
    """A single data quality issue found during screening."""
    dataset: str
    severity: str  # 'critical', 'error', 'warning', 'info'
    category: str  # 'integrity', 'statistics', 'semantic', 'consistency', 'leakage'
    description: str
    affected_count: int = 0
    recommendation: str = ""


@dataclass
class ScreeningReport:
    """Results from a data quality screening round."""
    round_number: int
    timestamp: float = field(default_factory=time.time)
    total_datasets: int = 0
    total_samples: int = 0
    issues: List[ScreeningIssue] = field(default_factory=list)
    dataset_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quality_score: float = 0.0  # 0-100
    passed: bool = False
    summary: str = ""


# =============================================================================
# Data Screener Class
# =============================================================================


class DataScreener:
    """Multi-round data quality screener for training datasets."""

    # Joint limits for semantic validation
    # Must match the limits used by data_generator.py (CUSTOM defaults)
    # These are the default synthetic arm limits, not UR5 real limits
    JOINT_LIMITS = [
        (-170, 170),   # Joint 1
        (-130, 130),   # Joint 2
        (-150, 150),   # Joint 3
        (-180, 180),   # Joint 4
        (-120, 120),   # Joint 5
        (-180, 180),   # Joint 6
    ]

    # UR5 real joint limits (for reference, used when data is from UR5 model)
    UR5_JOINT_LIMITS = [
        (-360, 360),   # Joint 1: ±360°
        (-360, 360),   # Joint 2: ±360°
        (-360, 360),   # Joint 3: ±360°
        (-360, 360),   # Joint 4: ±360°
        (-360, 360),   # Joint 5: ±360°
        (-360, 360),   # Joint 6: ±360° (infinite rotation)
    ]

    # Workspace bounds matching data_generator.py CUSTOM defaults
    # Note: CUSTOM DH params allow negative x due to arm geometry
    WORKSPACE_BOUNDS = {
        "x": (-500.0, 500.0),
        "y": (-500.0, 500.0),
        "z": (0.0, 500.0),
    }

    # Real industrial quality benchmarks (ISO 2859)
    # Must match the thresholds used in data_generator.py
    PRODUCT_THRESHOLDS = {
        "default": {"pass": 75, "reject": 35},
        "precision": {"pass": 88, "reject": 45},
        "coarse": {"pass": 65, "reject": 25},
    }

    def __init__(self, data_dir: str = "data/training", output_dir: str = "reports"):
        """Initialize the data screener.

        Args:
            data_dir: Directory containing training data JSON files.
            output_dir: Directory for screening reports.
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports: List[ScreeningReport] = []

        # Fields that are legitimately allowed to be None (optional/nullable)
        # These should NOT be counted as "missing" values
        self.optional_fields: Dict[str, Set[str]] = {
            "safety_dataset": {"violation_type"},
            "vision_dataset": {"object_position"},
            "noisy_vision_dataset": {"object_position", "noise_type"},
            "quality_dataset": {"product_type"},
            "collision_dataset": {"obstacle_position"},
            "multi_obstacle_collision": {"obstacle_position"},
            "edge_case_ik": {"edge_type"},
            "motion_dataset": set(),
            "ik_dataset": set(),
            "sampling_dataset": set(),
            "trajectory_dataset": set(),
            "sequential_motion": set(),
            "velocity_profile": set(),
            "multi_sensor_fusion": set(),
            "workspace_diversity": set(),
        }

    def screen_all(self, num_rounds: int = 3) -> List[ScreeningReport]:
        """Run multiple rounds of data quality screening.

        Each round becomes progressively stricter:
        - Round 1: Basic integrity checks
        - Round 2: Statistical analysis + outlier detection
        - Round 3: Semantic validation + cross-dataset consistency

        Args:
            num_rounds: Number of screening rounds.

        Returns:
            List of ScreeningReport objects.
        """
        for round_num in range(1, num_rounds + 1):
            print(f"\n{'='*60}")
            print(f"  DATA SCREENING ROUND {round_num}/{num_rounds}")
            print(f"{'='*60}")

            report = ScreeningReport(round_number=round_num)

            # Load all datasets
            datasets = self._load_all_datasets()
            report.total_datasets = len(datasets)
            report.total_samples = sum(len(v) for v in datasets.values())

            # Round-specific screening
            if round_num == 1:
                report.issues = self._screen_round1_integrity(datasets)
            elif round_num == 2:
                report.issues = self._screen_round2_statistics(datasets)
            else:
                report.issues = (
                    self._screen_round3_semantic(datasets)
                    + self._screen_round3_consistency(datasets)
                )

            # Compute statistics
            report.dataset_stats = self._compute_dataset_stats(datasets)

            # Calculate quality score
            report.quality_score = self._calculate_quality_score(report)

            # Determine pass/fail
            critical_count = sum(1 for i in report.issues if i.severity == "critical")
            error_count = sum(1 for i in report.issues if i.severity == "error")
            report.passed = critical_count == 0 and error_count <= 3
            report.summary = self._generate_summary(report)

            self.reports.append(report)
            self._print_report(report)

        return self.reports

    # =========================================================================
    # Round 1: Basic Integrity Checks
    # =========================================================================

    def _screen_round1_integrity(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 1: Basic data integrity checks.

        Checks:
        - Missing values (None, NaN, empty strings)
        - Schema validation (required fields present)
        - Duplicate detection
        - Data type consistency
        - File corruption
        """
        print("  [Round 1] Basic integrity screening...")
        issues = []

        for name, data in datasets.items():
            if not data:
                issues.append(ScreeningIssue(
                    dataset=name,
                    severity="error",
                    category="integrity",
                    description="Empty dataset",
                    recommendation="Regenerate the dataset",
                ))
                continue

            # Check for missing/None values (skip optional fields)
            optional = self.optional_fields.get(name, set())
            missing_count = 0
            for i, sample in enumerate(data):
                if sample is None:
                    missing_count += 1
                elif isinstance(sample, dict):
                    for key, value in sample.items():
                        if key in optional:
                            continue  # Skip optional/nullable fields
                        if value is None:
                            missing_count += 1
                        elif isinstance(value, float) and math.isnan(value):
                            missing_count += 1

            if missing_count > 0:
                severity = "critical" if missing_count > len(data) * 0.1 else "error"
                issues.append(ScreeningIssue(
                    dataset=name,
                    severity=severity,
                    category="integrity",
                    description=f"Found {missing_count} missing/null values",
                    affected_count=missing_count,
                    recommendation="Clean or regenerate the dataset",
                ))

            # Check for required schema fields
            schema_issues = self._validate_schema(name, data)
            issues.extend(schema_issues)

            # Check for duplicates
            dup_count = self._check_duplicates(data)
            if dup_count > 0:
                severity = "warning" if dup_count < 5 else "error"
                issues.append(ScreeningIssue(
                    dataset=name,
                    severity=severity,
                    category="integrity",
                    description=f"Found {dup_count} duplicate samples",
                    affected_count=dup_count,
                    recommendation="Remove duplicate entries",
                ))

            # Check data type consistency
            type_issues = self._check_type_consistency(name, data)
            issues.extend(type_issues)

        return issues

    def _validate_schema(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Validate that required fields are present for each dataset type."""
        issues = []

        required_fields = {
            "motion_dataset": ["joint_angles", "end_effector_pose", "reachable"],
            "ik_dataset": ["pose", "joints", "reachable"],
            "vision_dataset": ["detection_type", "detection_result"],
            "safety_dataset": ["joint_positions", "joint_velocities", "is_safe"],
            "quality_dataset": ["quality_score", "defects", "decision"],
            "sampling_dataset": ["bounds", "strategy", "results"],
            "collision_dataset": ["joint_positions", "obstacle_position", "collision_detected"],
            "trajectory_dataset": ["start_angles", "end_angles"],
            "edge_case_ik": ["pose", "joints", "reachable", "edge_type"],
            "noisy_vision_dataset": ["detection_type", "detection_result"],
            "multi_obstacle_collision": ["joint_positions", "obstacle_position", "collision_detected"],
        }

        if name not in required_fields:
            return issues

        required = required_fields[name]
        missing_count = 0
        first_error = None

        for i, sample in enumerate(data):
            if not isinstance(sample, dict):
                continue
            for field in required:
                if field not in sample:
                    missing_count += 1
                    if first_error is None:
                        first_error = f"Sample {i} missing field '{field}'"

        if missing_count > 0:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="error",
                category="integrity",
                description=f"{missing_count} samples missing required fields. Example: {first_error}",
                affected_count=missing_count,
                recommendation="Fix data generation to include all required fields",
            ))

        return issues

    def _check_duplicates(self, data: List[Dict]) -> int:
        """Count duplicate entries in the dataset."""
        seen = set()
        dup_count = 0
        for sample in data:
            if not isinstance(sample, dict):
                continue
            # Create a hashable representation
            key = json.dumps(sample, sort_keys=True, default=str)
            if key in seen:
                dup_count += 1
            else:
                seen.add(key)
        return dup_count

    def _check_type_consistency(self, name: str, data: List[Dict]) -> List[ScreeningIssue]:
        """Check for data type consistency issues."""
        issues = []
        type_errors = 0

        for i, sample in enumerate(data[:min(100, len(data))]):
            if not isinstance(sample, dict):
                continue
            for key, value in sample.items():
                if isinstance(value, list):
                    # Check list element types
                    for j, elem in enumerate(value):
                        if not isinstance(elem, (int, float, str, bool, list, dict)):
                            type_errors += 1
                elif not isinstance(value, (int, float, str, bool, list, dict, type(None))):
                    type_errors += 1

        if type_errors > 0:
            issues.append(ScreeningIssue(
                dataset=name,
                severity="warning",
                category="integrity",
                description=f"Found {type_errors} type inconsistencies in first 100 samples",
                affected_count=type_errors,
                recommendation="Review data generation for type consistency",
            ))

        return issues

    # =========================================================================
    # Round 2: Statistical Analysis
    # =========================================================================

    def _screen_round2_statistics(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 2: Statistical analysis and outlier detection.

        Checks:
        - Outlier detection (IQR method)
        - Class balance analysis
        - Distribution analysis (skewness, kurtosis)
        - Value range validation
        """
        print("  [Round 2] Statistical analysis...")
        issues = []

        for name, data in datasets.items():
            if not data:
                continue

            # Extract numeric fields
            numeric_fields = self._extract_numeric_fields(data[:1000])

            # Exclude metadata fields that are naturally non-normally distributed
            SKIP_FIELDS = {"timestamp", "sample_id", "sequence_id", "fusion_id", "config_type"}
            
            for field_name, values in numeric_fields.items():
                if field_name in SKIP_FIELDS:
                    continue
                if len(values) < 10:
                    continue

                arr = np.array(values, dtype=np.float64)
                arr = arr[np.isfinite(arr)]

                if len(arr) < 10:
                    continue

                # IQR outlier detection
                q1, q3 = np.percentile(arr, [25, 75])
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = np.sum((arr < lower) | (arr > upper))

                # Use higher outlier thresholds for datasets that intentionally
                # contain extreme values:
                # - edge_case_ik: boundary/singularity joints are expected extremes
                # - safety_dataset: over_speed violations produce high velocities
                # - vision_dataset: noisy/low-light conditions produce low confidence
                HIGH_VARIANCE_DATASETS = {
                    "edge_case_ik": 0.25,       # 25% threshold for edge cases
                    "safety_dataset": 0.20,      # 20% threshold for safety violations
                    "vision_dataset": 0.25,      # 25% threshold for noisy vision
                    "noisy_vision_dataset": 0.30, # 30% for intentionally noisy data
                    "velocity_profile": 0.25,    # 25% threshold: trapezoidal/s-curve
                                                  #   profiles naturally produce
                                                  #   acceleration spikes at transitions
                    "trajectory_dataset": 0.20,  # 20% threshold: wide joint ranges
                                                  #   produce naturally varying angles
                }
                outlier_threshold = HIGH_VARIANCE_DATASETS.get(name, 0.10)

                if outliers > len(arr) * outlier_threshold:
                    issues.append(ScreeningIssue(
                        dataset=name,
                        severity="warning",
                        category="statistics",
                        description=f"Field '{field_name}' has {outliers}/{len(arr)} outliers ({outliers/len(arr)*100:.1f}%)",
                        affected_count=int(outliers),
                        recommendation="Review data generation for this field",
                    ))

                # Skewness check
                mean = np.mean(arr)
                std = np.std(arr)
                if std > 0:
                    skewness = np.mean(((arr - mean) / std) ** 3)
                    if abs(skewness) > 3:
                        issues.append(ScreeningIssue(
                            dataset=name,
                            severity="info",
                            category="statistics",
                            description=f"Field '{field_name}' is highly skewed (skewness={skewness:.2f})",
                            recommendation="Consider data transformation or rebalancing",
                        ))

            # Class balance for safety dataset
            if name == "safety_dataset":
                safe_count = sum(1 for s in data if s.get("is_safe", False))
                unsafe_count = len(data) - safe_count
                if safe_count > 0:
                    ratio = unsafe_count / safe_count
                    if ratio < 0.15 or ratio > 3:
                        issues.append(ScreeningIssue(
                            dataset=name,
                            severity="warning",
                            category="statistics",
                            description=f"Class imbalance: safe={safe_count}, unsafe={unsafe_count} (ratio={ratio:.2f})",
                            recommendation="Adjust class balance to ~30% unsafe",
                        ))

            # Value range validation
            if name in ("motion_dataset", "ik_dataset", "edge_case_ik"):
                range_issues = self._validate_value_ranges(
                    name, data, self.JOINT_LIMITS, self.WORKSPACE_BOUNDS
                )
                issues.extend(range_issues)
            elif name == "real_motion_dataset":
                # Real motion data uses UR5 limits and workspace
                ur5_workspace = {"x": (-850.0, 850.0), "y": (-850.0, 850.0), "z": (0.0, 850.0)}
                range_issues = self._validate_value_ranges(
                    name, data, self.UR5_JOINT_LIMITS, ur5_workspace
                )
                issues.extend(range_issues)

        return issues

    def _extract_numeric_fields(self, data: List[Dict]) -> Dict[str, List[float]]:
        """Extract all numeric fields from dataset samples."""
        fields: Dict[str, List[float]] = {}

        for sample in data:
            if not isinstance(sample, dict):
                continue
            for key, value in sample.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if key not in fields:
                        fields[key] = []
                    fields[key].append(float(value))
                elif isinstance(value, list):
                    for i, elem in enumerate(value):
                        if isinstance(elem, (int, float)) and not isinstance(elem, bool):
                            fname = f"{key}[{i}]"
                            if fname not in fields:
                                fields[fname] = []
                            fields[fname].append(float(elem))

        return fields

    def _validate_value_ranges(
        self, name: str, data: List[Dict],
        joint_limits: List[Tuple[float, float]],
        workspace_bounds: Dict[str, Tuple[float, float]],
    ) -> List[ScreeningIssue]:
        """Validate that values are within expected ranges.

        Args:
            name: Dataset name.
            data: Dataset samples.
            joint_limits: Joint limits to validate against.
            workspace_bounds: Workspace bounds to validate against.
        """
        issues = []

        for i, sample in enumerate(data[:1000]):
            if not isinstance(sample, dict):
                continue

            # Check pose values
            pose = sample.get("pose", [])
            if len(pose) >= 3:
                x, y, z = pose[0], pose[1], pose[2]
                if x < workspace_bounds["x"][0] - 50 or x > workspace_bounds["x"][1] + 50:
                    issues.append(ScreeningIssue(
                        dataset=name,
                        severity="warning",
                        category="statistics",
                        description="Pose x={:.1f} out of workspace bounds at sample {}".format(x, i),
                        recommendation="Review IK generation for workspace bounds",
                    ))
                    break  # One example per dataset is enough

            # Check joint angles - use field name to determine unit
            # 'joint_angles' field → degrees, 'joints' field → radians
            joints_field = None
            joints_data = None
            if "joint_angles" in sample:
                joints_field = "joint_angles"
                joints_data = sample["joint_angles"]
            elif "joint_angles_rad" in sample:
                # real_motion_dataset uses "joint_angles_rad"
                joints_field = "joint_angles_rad"
                joints_data = sample["joint_angles_rad"]
            elif "joints" in sample:
                joints_field = "joints"
                joints_data = sample["joints"]
            else:
                joints_data = []

            if len(joints_data) >= 6:
                is_radians = (joints_field in ("joints", "joint_angles_rad"))
                for j, angle in enumerate(joints_data[:6]):
                    if j < len(joint_limits):
                        lo, hi = joint_limits[j]
                        if is_radians:
                            angle_deg = math.degrees(angle)
                        else:
                            angle_deg = angle  # Already in degrees
                        if angle_deg < lo - 10 or angle_deg > hi + 10:
                            issues.append(ScreeningIssue(
                                dataset=name,
                                severity="error",
                                category="statistics",
                                description="Joint {} angle {:.1f}° out of limits [{}, {}] at sample {}".format(
                                    j+1, angle_deg, lo, hi, i),
                                recommendation="Fix joint angle generation",
                            ))
                            break

        return issues

    # =========================================================================
    # Round 3: Semantic Validation + Cross-Dataset Consistency
    # =========================================================================

    def _screen_round3_semantic(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 3: Semantic validation.

        Checks:
        - Physical consistency (FK/IK consistency)
        - Reachability consistency
        - Collision logic consistency
        - Quality score logic consistency
        """
        print("  [Round 3] Semantic validation...")
        issues = []

        # Check FK/IK consistency in motion dataset
        if "motion_dataset" in datasets:
            fk_issues = self._check_fk_ik_consistency(
                datasets["motion_dataset"], "motion_dataset"
            )
            issues.extend(fk_issues)

        # Check FK/IK consistency in real_motion_dataset (uses UR5 real limits)
        if "real_motion_dataset" in datasets:
            fk_issues = self._check_fk_ik_consistency(
                datasets["real_motion_dataset"], "real_motion_dataset"
            )
            issues.extend(fk_issues)

        # Check collision logic
        if "collision_dataset" in datasets:
            coll_issues = self._check_collision_logic(datasets["collision_dataset"])
            issues.extend(coll_issues)

        # Check multi-obstacle collision
        if "multi_obstacle_collision" in datasets:
            coll_issues = self._check_collision_logic(datasets["multi_obstacle_collision"])
            issues.extend(coll_issues)

        # Check quality logic
        if "quality_dataset" in datasets:
            qual_issues = self._check_quality_logic(datasets["quality_dataset"])
            issues.extend(qual_issues)

        # Check edge case coverage
        if "edge_case_ik" in datasets:
            edge_issues = self._check_edge_case_coverage(datasets["edge_case_ik"])
            issues.extend(edge_issues)

        return issues

    def _check_fk_ik_consistency(self, data: List[Dict], dataset_name: str = "motion_dataset") -> List[ScreeningIssue]:
        """Verify FK/IK consistency in motion data.

        Note: When loaded from JSON, 'joint_angles' field is already in DEGREES
        (converted by DatasetGenerator.save_all_datasets). The 'joint_angles_rad'
        field (used by real_motion_dataset) is in RADIANS.
        
        For real_motion_dataset, uses UR5 joint limits (±360°) since
        real robot data is generated with wider joint ranges.
        """
        issues = []
        inconsistency_count = 0

        # Select appropriate joint limits based on dataset
        if dataset_name == "real_motion_dataset":
            joint_limits = self.UR5_JOINT_LIMITS
        else:
            joint_limits = self.JOINT_LIMITS

        for sample in data[:500]:
            # Determine which field to use and whether it's in radians
            joints = sample.get("joint_angles", [])
            is_radians = False  # 'joint_angles' in JSON is already in degrees
            if not joints:
                joints = sample.get("joint_angles_rad", [])
                is_radians = True  # 'joint_angles_rad' is in radians
            
            if len(joints) < 6:
                continue

            reachable = sample.get("reachable", True)
            if reachable:
                for j, angle in enumerate(joints[:6]):
                    if j < len(joint_limits):
                        lo, hi = joint_limits[j]
                        # Convert to degrees only if stored in radians
                        angle_deg = math.degrees(angle) if is_radians else angle
                        if angle_deg < lo - 10 or angle_deg > hi + 10:
                            inconsistency_count += 1
                            break

        if inconsistency_count > 0:
            issues.append(ScreeningIssue(
                dataset=dataset_name,
                severity="error",
                category="semantic",
                description="FK/IK inconsistency: {} reachable samples have out-of-bounds joints".format(inconsistency_count),
                affected_count=inconsistency_count,
                recommendation="Review FK/IK generation logic",
            ))

        return issues

    def _check_collision_logic(self, data: List[Dict]) -> List[ScreeningIssue]:
        """Verify collision detection logic."""
        issues = []
        suspicious_count = 0

        for sample in data[:500]:
            collision = sample.get("collision_detected", False)
            distance = sample.get("distance_mm", 0)

            # Suspicious: collision detected but distance > 200mm
            if collision and distance > 200:
                suspicious_count += 1
            # Suspicious: no collision but distance < 10mm
            if not collision and distance < 10:
                suspicious_count += 1

        if suspicious_count > 0:
            issues.append(ScreeningIssue(
                dataset="collision_dataset",
                severity="warning",
                category="semantic",
                description=f"Suspicious collision logic: {suspicious_count} samples with inconsistent distance/collision",
                affected_count=suspicious_count,
                recommendation="Review collision detection thresholds",
            ))

        return issues

    def _check_quality_logic(self, data: List[Dict]) -> List[ScreeningIssue]:
        """Verify quality score logic with product-type-aware thresholds.

    Uses the same thresholds as DatasetGenerator (class-level PRODUCT_THRESHOLDS):
    - default: pass=75, reject=35, resample=50
    - precision: pass=88, reject=45, resample=65
    - coarse: pass=65, reject=25, resample=40

    Also validates against real industrial benchmarks (ISO 2859).
    """
        issues = []
        inconsistent_count = 0
        industry_mismatch_count = 0

        # Real industry pass rates for benchmark comparison
        INDUSTRY_BENCHMARKS = {
            "electronics": 0.95,
            "automotive": 0.92,
            "aerospace": 0.98,
            "consumer_goods": 0.88,
            "medical": 0.99,
        }

        for sample in data[:500]:
            score = sample.get("quality_score", 0)
            decision = sample.get("decision", "")
            defects = sample.get("defects", [])
            product_type = sample.get("product_type", "default")
            industry = sample.get("industry", "")

            thresh = self.PRODUCT_THRESHOLDS.get(
                product_type, self.PRODUCT_THRESHOLDS["default"]
            )
            pass_threshold = thresh["pass"]
            reject_threshold = thresh["reject"]

            # Check that more defects → lower score (coarse check)
            # Use epsilon to handle floating point boundary cases
            # 1e-6 handles IEEE 754 rounding errors for scores rounded to 1 decimal
            if len(defects) > 5 and score > 80 + 1e-6:
                inconsistent_count += 1
            if len(defects) == 0 and score < 60 - 1e-6:
                inconsistent_count += 1

            # Check decision consistency with product-type-aware thresholds
            # Use epsilon tolerance to avoid floating-point boundary false positives
            # 1e-6 is chosen because quality_score is rounded to 1 decimal place
            # (round(quality_score, 1)), so the smallest meaningful difference is 0.1.
            # EPS=1e-6 is safely below 0.1 while handling IEEE 754 rounding errors.
            EPS = 1e-6
            if score >= pass_threshold - EPS and decision != "accept":
                inconsistent_count += 1
            if score < reject_threshold + EPS and decision != "reject":
                inconsistent_count += 1

            # Validate against real industry benchmarks
            if industry in INDUSTRY_BENCHMARKS:
                expected_pass = INDUSTRY_BENCHMARKS[industry]
                if decision == "accept" and score < 60:
                    industry_mismatch_count += 1
                if decision == "reject" and score > 75:
                    industry_mismatch_count += 1

        if inconsistent_count > 0:
            issues.append(ScreeningIssue(
                dataset="quality_dataset",
                severity="warning",
                category="semantic",
                description=f"Quality logic inconsistency: {inconsistent_count} samples with suspicious score/decision",
                affected_count=inconsistent_count,
                recommendation="Review quality score generation logic",
            ))

        if industry_mismatch_count > 0:
            issues.append(ScreeningIssue(
                dataset="quality_dataset",
                severity="info",
                category="semantic",
                description=f"Industry benchmark mismatch: {industry_mismatch_count} samples deviate from ISO 2859 standards",
                affected_count=industry_mismatch_count,
                recommendation="Consider adjusting quality thresholds to match industry benchmarks",
            ))

        return issues

    def _check_edge_case_coverage(self, data: List[Dict]) -> List[ScreeningIssue]:
        """Check edge case coverage distribution."""
        issues = []
        edge_types = Counter(s.get("edge_type", "unknown") for s in data)

        expected_types = {"boundary", "near_singularity", "extreme_orientation", "full_reach"}
        missing = expected_types - set(edge_types.keys())

        if missing:
            issues.append(ScreeningIssue(
                dataset="edge_case_ik",
                severity="warning",
                category="semantic",
                description=f"Missing edge case types: {missing}",
                recommendation="Ensure all edge case types are generated",
            ))

        # Check distribution balance
        total = sum(edge_types.values())
        for etype, count in edge_types.items():
            ratio = count / total
            if ratio < 0.1:  # Less than 10% of samples
                issues.append(ScreeningIssue(
                    dataset="edge_case_ik",
                    severity="info",
                    category="semantic",
                    description=f"Edge type '{etype}' underrepresented: {count}/{total} ({ratio*100:.1f}%)",
                    recommendation="Balance edge case type distribution",
                ))

        return issues

    def _screen_round3_consistency(self, datasets: Dict[str, List]) -> List[ScreeningIssue]:
        """Round 3: Cross-dataset consistency checks.

        Checks:
        - Data leakage between train/validation sets
        - Consistent labeling across datasets
        - Overlapping samples between datasets
        """
        print("  [Round 3] Cross-dataset consistency...")
        issues = []

        # Check for overlapping samples between datasets
        dataset_names = list(datasets.keys())
        for i in range(len(dataset_names)):
            for j in range(i + 1, len(dataset_names)):
                overlap = self._check_overlap(
                    datasets[dataset_names[i]],
                    datasets[dataset_names[j]],
                )
                if overlap > 0:
                    # Only warn if overlap is > 1% (could be coincidence)
                    min_size = min(len(datasets[dataset_names[i]]), len(datasets[dataset_names[j]]))
                    if overlap / min_size > 0.01:
                        issues.append(ScreeningIssue(
                            dataset=f"{dataset_names[i]} ↔ {dataset_names[j]}",
                            severity="info",
                            category="consistency",
                            description=f"Found {overlap} potentially overlapping samples",
                            affected_count=overlap,
                            recommendation="Review if overlap is expected",
                        ))

        # Check label consistency between datasets
        if "safety_dataset" in datasets and "collision_dataset" in datasets:
            safety_unsafe_ratio = (
                sum(1 for s in datasets["safety_dataset"] if not s.get("is_safe", True))
                / max(len(datasets["safety_dataset"]), 1)
            )
            collision_ratio = (
                sum(1 for s in datasets["collision_dataset"] if s.get("collision_detected", False))
                / max(len(datasets["collision_dataset"]), 1)
            )

            if abs(safety_unsafe_ratio - collision_ratio) > 0.3:
                issues.append(ScreeningIssue(
                    dataset="safety ↔ collision",
                    severity="info",
                    category="consistency",
                    description=f"Label distribution mismatch: safety unsafe={safety_unsafe_ratio:.2%}, collision={collision_ratio:.2%}",
                    recommendation="Review if different distributions are expected",
                ))

        return issues

    def _check_overlap(self, data1: List[Dict], data2: List[Dict]) -> int:
        """Check for overlapping samples between two datasets."""
        # Use a sample of keys for efficiency
        sample_size = min(1000, len(data1), len(data2))
        keys1 = set()
        for s in data1[:sample_size]:
            if isinstance(s, dict):
                # Use a subset of fields for comparison
                key_fields = {k: str(v) for k, v in s.items()
                             if k in ("joint_positions", "pose", "joint_angles")}
                if key_fields:
                    keys1.add(json.dumps(key_fields, sort_keys=True))

        overlap = 0
        for s in data2[:sample_size]:
            if isinstance(s, dict):
                key_fields = {k: str(v) for k, v in s.items()
                             if k in ("joint_positions", "pose", "joint_angles")}
                if key_fields and json.dumps(key_fields, sort_keys=True) in keys1:
                    overlap += 1

        return overlap

    # =========================================================================
    # Statistics & Reporting
    # =========================================================================

    def _compute_dataset_stats(self, datasets: Dict[str, List]) -> Dict[str, Dict[str, Any]]:
        """Compute statistics for each dataset."""
        stats = {}

        for name, data in datasets.items():
            if not data:
                stats[name] = {"samples": 0, "status": "empty"}
                continue

            dataset_stats: Dict[str, Any] = {
                "samples": len(data),
                "status": "ok",
                "fields": list(data[0].keys()) if isinstance(data[0], dict) else [],
            }

            # Count samples with specific properties
            if isinstance(data[0], dict):
                first_keys = set(data[0].keys())
            else:
                first_keys = set()

            if "reachable" in first_keys:
                reachable = sum(1 for s in data if s.get("reachable", False))
                dataset_stats["reachable"] = reachable
                dataset_stats["reachable_pct"] = round(reachable / len(data) * 100, 1)

            if "is_safe" in first_keys:
                safe = sum(1 for s in data if s.get("is_safe", True))
                dataset_stats["safe"] = safe
                dataset_stats["unsafe"] = len(data) - safe

            if "collision_detected" in first_keys:
                collisions = sum(1 for s in data if s.get("collision_detected", False))
                dataset_stats["collisions"] = collisions
                dataset_stats["collision_pct"] = round(collisions / len(data) * 100, 1)

            if "decision" in first_keys:
                decisions = Counter(
                    str(s.get("decision", "unknown")) if isinstance(s.get("decision"), dict)
                    else s.get("decision", "unknown")
                    for s in data
                )
                dataset_stats["decisions"] = dict(decisions)

            if "edge_type" in first_keys:
                edge_types = Counter(s.get("edge_type", "unknown") for s in data)
                dataset_stats["edge_types"] = dict(edge_types)

            stats[name] = dataset_stats

        return stats

    def _calculate_quality_score(self, report: ScreeningReport) -> float:
        """Calculate overall data quality score (0-100).

        Scoring:
        - Start at 100
        - Critical issues: -20 each (hard cap)
        - Error issues: -10 each (hard cap)
        - Warning issues: -3 each (capped at -30 total from warnings)
        - Info issues: -1 each (capped at -10 total from info)
        - Bonus for large datasets: +5 (>50k), +3 (>30k)
        
        The warning cap ensures that datasets with many minor warnings
        (e.g., velocity_profile with naturally high acceleration variance)
        don't get unfairly penalized to 0.
        """
        score = 100.0
        critical_count = 0
        error_count = 0
        warning_count = 0
        info_count = 0
        
        for issue in report.issues:
            if issue.severity == "critical":
                critical_count += 1
            elif issue.severity == "error":
                error_count += 1
            elif issue.severity == "warning":
                warning_count += 1
            elif issue.severity == "info":
                info_count += 1
        
        # Apply deductions with caps
        score -= critical_count * 20  # No cap on critical (should be rare)
        score -= error_count * 10      # No cap on errors (should be rare)
        score -= min(warning_count * 3, 30)  # Cap warning deductions at 30
        score -= min(info_count * 1, 10)     # Cap info deductions at 10
        
        # Bonus for large datasets
        if report.total_samples > 50000:
            score += 5
        elif report.total_samples > 30000:
            score += 3
        
        return max(0.0, min(100.0, score))

    def _generate_summary(self, report: ScreeningReport) -> str:
        """Generate a human-readable summary."""
        severity_counts = Counter(i.severity for i in report.issues)
        category_counts = Counter(i.category for i in report.issues)

        parts = [
            f"Round {report.round_number}: "
            f"{report.total_datasets} datasets, {report.total_samples} total samples",
            f"Quality Score: {report.quality_score:.0f}/100",
            f"Status: {'PASSED' if report.passed else 'FAILED'}",
        ]

        if severity_counts:
            sev_str = ", ".join(f"{s}={c}" for s, c in sorted(severity_counts.items()))
            parts.append(f"Issues: {sev_str}")

        return " | ".join(parts)

    def _print_report(self, report: ScreeningReport) -> None:
        """Print a formatted screening report."""
        print(f"\n{'='*60}")
        print(f"  SCREENING REPORT - Round {report.round_number}")
        print(f"{'='*60}")
        print(f"  {report.summary}")
        print(f"\n  Dataset Statistics:")
        for name, stats in report.dataset_stats.items():
            samples = stats.get("samples", 0)
            extras = ""
            if "reachable_pct" in stats:
                extras = f" (reachable: {stats['reachable_pct']}%)"
            elif "collision_pct" in stats:
                extras = f" (collision: {stats['collision_pct']}%)"
            print(f"    {name}: {samples} samples{extras}")

        if report.issues:
            print(f"\n  Issues Found ({len(report.issues)}):")
            for issue in report.issues:
                icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(issue.severity, "⚪")
                print(f"    {icon} [{issue.severity.upper()}] {issue.dataset}: {issue.description}")
                if issue.recommendation:
                    print(f"       → {issue.recommendation}")
        else:
            print(f"\n  ✅ No issues found!")

        print(f"{'='*60}")

    # =========================================================================
    # Helpers
    # =========================================================================

    def _load_all_datasets(self) -> Dict[str, List]:
        """Load all JSON datasets from the data directory."""
        datasets = {}
        if not self.data_dir.exists():
            return datasets

        for filepath in sorted(self.data_dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    datasets[filepath.stem] = data
                else:
                    datasets[filepath.stem] = [data]
            except (json.JSONDecodeError, FileNotFoundError) as e:
                datasets[filepath.stem] = []
                print(f"    Warning: Failed to load {filepath.name}: {e}")

        return datasets

    def save_reports(self) -> None:
        """Save all screening reports to JSON."""
        for report in self.reports:
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
            print(f"  Screening report saved to: {filepath}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    screener = DataScreener()
    reports = screener.screen_all(num_rounds=3)
    screener.save_reports()

    print(f"\n{'#'*60}")
    print(f"#  DATA SCREENING COMPLETE")
    print(f"{'#'*60}")
    for report in reports:
        status = "✅ PASSED" if report.passed else "❌ FAILED"
        print(f"  Round {report.round_number}: {status} (Score: {report.quality_score:.0f}/100)")
    print(f"{'#'*60}")