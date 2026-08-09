"""
Quality Inspection Agent for the Intelligent Sampling Robotic Arm.

Evaluates the quality of sampled objects, classifies defects, makes
accept/reject decisions, and generates structured inspection reports.
Maintains running statistics for process monitoring and triggers
re-sampling when quality is insufficient.

Quality thresholds are configurable per product type.
"""

import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .base_agent import BaseAgent, AgentConfig, validate_state, log_execution


class QualityDecision(Enum):
    """Accept/reject decisions for inspected samples."""
    ACCEPT = "accept"
    REJECT = "reject"
    REWORK = "rework"
    RESAMPLE = "resample"
    PENDING = "pending"


class DefectType(Enum):
    """Types of defects that can be detected."""
    SCRATCH = "scratch"
    DISCOLORATION = "discoloration"
    DIMENSION_ERROR = "dimension_error"
    SURFACE_DEFECT = "surface_defect"
    COLOR_INCONSISTENCY = "color_inconsistency"
    MISSING_FEATURE = "missing_feature"
    CONTAMINATION = "contamination"
    DEFORMATION = "deformation"


class QualityAgent(BaseAgent):
    """Agent for quality inspection and decision-making.

    Processes inspection results from the OpenMV camera, computes quality
    scores, classifies defects, and makes accept/reject decisions. Maintains
    statistical process control (SPC) data for trend analysis.

    Attributes:
        quality_thresholds: Per-product quality thresholds.
        inspection_history: List of recent inspection results.
        spc_data: Running statistics for process monitoring.
        defect_counts: Running count of defects by type.
    """

    def __init__(
        self,
        name: str = "quality_agent",
        config: Optional[AgentConfig] = None,
    ) -> None:
        """Initialize the quality agent.

        Args:
            name: Agent name.
            config: Agent configuration.
        """
        super().__init__(name, config)
        self.quality_thresholds: Dict[str, Dict[str, float]] = {
            "default": {
                "pass_score": 70.0,
                "resample_score": 50.0,
                "reject_score": 30.0,
                "dimension_tolerance_mm": 2.0,
                "max_defects": 3,
            },
            "precision": {
                "pass_score": 85.0,
                "resample_score": 65.0,
                "reject_score": 40.0,
                "dimension_tolerance_mm": 0.5,
                "max_defects": 1,
            },
            "coarse": {
                "pass_score": 60.0,
                "resample_score": 40.0,
                "reject_score": 20.0,
                "dimension_tolerance_mm": 5.0,
                "max_defects": 5,
            },
        }
        self.inspection_history: List[Dict[str, Any]] = []
        self.max_history: int = 1000
        self.spc_data: Dict[str, List[float]] = {
            "scores": [],
            "defect_counts": [],
        }
        self.defect_counts: Dict[str, int] = {d.value: 0 for d in DefectType}
        self._archived_stats: Optional[Dict[str, Any]] = None  # SPC aggregation

    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate quality inspection state.

        Args:
            state: Current system state.

        Returns:
            True if valid.
        """
        return True

    @validate_state(required_keys=["sample_id", "inspection_result"])
    @log_execution
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process a quality inspection result.

        Args:
            state: Must contain 'sample_id' and 'inspection_result'.

        Returns:
            State with quality decision and report.
        """
        sample_id = state.get("sample_id", "unknown")
        inspection_result = state.get("inspection_result", {})
        product_type = state.get("product_type", "default")

        # Evaluate quality
        quality_score = self.evaluate_quality(inspection_result)

        # Classify defects
        defects = self.classify_defects(inspection_result)

        # Make decision
        decision = self.decide_accept_reject(quality_score, product_type)

        # Check if resampling is needed
        resample_needed = self.trigger_resampling(quality_score, product_type)

        # Generate report
        report = self.generate_inspection_report(sample_id)

        # Update statistics
        self.update_quality_stats({
            "sample_id": sample_id,
            "quality_score": quality_score,
            "decision": decision.value,
            "defects": defects,
            "product_type": product_type,
        })

        state["quality_score"] = quality_score
        state["quality_decision"] = decision.value
        state["quality_defects"] = defects
        state["quality_report"] = report
        state["resample_needed"] = resample_needed

        return state

    # =========================================================================
    # Quality Evaluation
    # =========================================================================

    def evaluate_quality(self, inspection_result: Dict[str, Any]) -> float:
        """Compute a quality score from inspection results.

        Combines surface quality, dimensional accuracy, and color consistency
        into a single score from 0 to 100.

        Args:
            inspection_result: Dict from OpenMV quality inspection.

        Returns:
            Quality score (0-100).
        """
        if not inspection_result:
            return 0.0

        # If the OpenMV already computed a score, use it
        if "score" in inspection_result:
            return float(inspection_result["score"])

        # Otherwise compute from sub-scores
        surface_score = inspection_result.get("surface_score", 100.0)
        dimension_score = 100.0

        if "dimensions" in inspection_result:
            dim = inspection_result["dimensions"]
            if dim.get("dimension_score"):
                dimension_score = dim["dimension_score"]

        color_score = 100.0
        if "color_consistency" in inspection_result:
            cc = inspection_result["color_consistency"]
            if cc.get("consistency_score"):
                color_score = cc["consistency_score"]

        # Weighted combination
        overall = 0.4 * surface_score + 0.3 * dimension_score + 0.3 * color_score
        return round(min(100.0, max(0.0, overall)), 1)

    # =========================================================================
    # Defect Classification
    # =========================================================================

    def classify_defects(self, inspection_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Classify detected defects into known categories.

        Args:
            inspection_result: Inspection result from OpenMV.

        Returns:
            List of classified defect dicts.
        """
        classified = []
        raw_defects = inspection_result.get("defects", [])

        for defect in raw_defects:
            defect_type = defect.get("type", "unknown")
            severity = defect.get("severity", "minor")

            # Map raw defect types to standard categories
            category = self._map_defect_type(defect_type)
            classified.append({
                "type": category.value,
                "severity": severity,
                "position": (defect.get("cx", 0), defect.get("cy", 0)),
                "area": defect.get("area", 0),
                "metadata": defect,
            })

            # Update defect counter
            self.defect_counts[category.value] = self.defect_counts.get(category.value, 0) + 1

        return classified

    def _map_defect_type(self, raw_type: str) -> DefectType:
        """Map a raw defect type string to a DefectType enum.

        Args:
            raw_type: Raw defect type from OpenMV.

        Returns:
            Mapped DefectType.
        """
        mapping = {
            "scratch": DefectType.SCRATCH,
            "spot": DefectType.SURFACE_DEFECT,
            "discoloration": DefectType.DISCOLORATION,
            "dimension": DefectType.DIMENSION_ERROR,
            "color": DefectType.COLOR_INCONSISTENCY,
            "contamination": DefectType.CONTAMINATION,
            "deformation": DefectType.DEFORMATION,
        }
        return mapping.get(raw_type, DefectType.SURFACE_DEFECT)

    # =========================================================================
    # Decision Making
    # =========================================================================

    def decide_accept_reject(
        self,
        quality_score: float,
        product_type: str = "default",
    ) -> QualityDecision:
        """Make an accept/reject decision based on quality score.

        Args:
            quality_score: Computed quality score (0-100).
            product_type: Product type for threshold lookup.

        Returns:
            QualityDecision enum value.
        """
        thresholds = self.quality_thresholds.get(product_type, self.quality_thresholds["default"])
        pass_score = thresholds["pass_score"]
        reject_score = thresholds["reject_score"]

        if quality_score >= pass_score:
            return QualityDecision.ACCEPT
        elif quality_score >= reject_score:
            return QualityDecision.REWORK
        else:
            return QualityDecision.REJECT

    def trigger_resampling(
        self,
        quality_score: float,
        product_type: str = "default",
    ) -> bool:
        """Determine if re-sampling is needed based on quality score.

        Resampling is triggered when the quality score is between the
        reject and resample thresholds.

        Args:
            quality_score: Computed quality score.
            product_type: Product type for threshold lookup.

        Returns:
            True if resampling is recommended.
        """
        thresholds = self.quality_thresholds.get(product_type, self.quality_thresholds["default"])
        resample_score = thresholds["resample_score"]
        reject_score = thresholds["reject_score"]

        return reject_score <= quality_score < resample_score

    # =========================================================================
    # Reporting
    # =========================================================================

    def generate_inspection_report(self, sample_id: str) -> Dict[str, Any]:
        """Generate a structured inspection report for a sample.

        Args:
            sample_id: Sample identifier.

        Returns:
            Structured report dict.
        """
        # Get the most recent inspection matching this sample
        recent = None
        for entry in reversed(self.inspection_history):
            if entry.get("sample_id") == sample_id:
                recent = entry
                break

        if recent is None:
            return {
                "sample_id": sample_id,
                "timestamp": time.time(),
                "status": "no_data",
                "message": "No inspection data available",
            }

        return {
            "sample_id": sample_id,
            "timestamp": recent.get("timestamp", time.time()),
            "quality_score": recent.get("quality_score", 0.0),
            "decision": recent.get("decision", "unknown"),
            "defect_count": len(recent.get("defects", [])),
            "defects": recent.get("defects", []),
            "product_type": recent.get("product_type", "default"),
            "status": "pass" if recent.get("decision") == "accept" else "fail",
        }

    # =========================================================================
    # Statistics
    # =========================================================================

    def update_quality_stats(self, sample_data: Dict[str, Any]) -> None:
        """Update running quality statistics with new sample data.

        Uses optimized data retention: keeps a sliding window of recent
        samples plus statistical summaries of older data for long-term
        trend analysis without memory bloat.

        Args:
            sample_data: Dict with quality data for one sample.
        """
        sample_data["timestamp"] = time.time()
        self.inspection_history.append(sample_data)

        # Optimized trim: keep recent data, aggregate old data
        if len(self.inspection_history) > self.max_history:
            # Keep the most recent 80% of max_history
            keep_count = int(self.max_history * 0.8)
            old_data = self.inspection_history[:-keep_count]
            recent_data = self.inspection_history[-keep_count:]

            # Aggregate old data into summary statistics
            if old_data:
                old_scores = [s.get("quality_score", 0) for s in old_data]
                self._archived_stats = {
                    "count": len(old_scores),
                    "mean": float(np.mean(old_scores)),
                    "std": float(np.std(old_scores)),
                    "min": float(np.min(old_scores)),
                    "max": float(np.max(old_scores)),
                    "last_archived": time.time(),
                }

            self.inspection_history = recent_data

        # Update SPC data with bounded window
        score = sample_data.get("quality_score", 0)
        self.spc_data["scores"].append(score)
        self.spc_data["defect_counts"].append(len(sample_data.get("defects", [])))

        # Keep SPC data bounded with optimized window
        max_spc = 500
        if len(self.spc_data["scores"]) > max_spc:
            self.spc_data["scores"] = self.spc_data["scores"][-max_spc:]
            self.spc_data["defect_counts"] = self.spc_data["defect_counts"][-max_spc:]

        # Check for SPC anomalies (out-of-control signals)
        if len(self.spc_data["scores"]) >= 20:
            self._check_spc_anomalies()

    def _check_spc_anomalies(self) -> Optional[Dict[str, Any]]:
        """Check for SPC (Statistical Process Control) anomalies.

        Detects:
        - 7 consecutive points on same side of mean (trend)
        - Sudden score drop (>2σ from mean)
        - Increasing defect rate

        Returns:
            Anomaly report dict or None.
        """
        scores = self.spc_data["scores"]
        if len(scores) < 20:
            return None

        arr = np.array(scores[-20:])
        mean = np.mean(arr)
        std = np.std(arr) + 1e-8

        anomalies = []

        # Rule 1: 7 consecutive points on same side of mean
        recent = arr[-7:]
        if all(r > mean for r in recent):
            anomalies.append({"type": "trend_up", "desc": "7 consecutive points above mean"})
        elif all(r < mean for r in recent):
            anomalies.append({"type": "trend_down", "desc": "7 consecutive points below mean"})

        # Rule 2: Sudden drop (>2σ)
        if arr[-1] < mean - 2 * std:
            anomalies.append({"type": "sharp_drop", "desc": f"Score {arr[-1]:.1f} >2σ below mean {mean:.1f}"})

        # Rule 3: Increasing defect rate
        defect_counts = self.spc_data["defect_counts"][-20:]
        if len(defect_counts) >= 10:
            first_half = np.mean(defect_counts[:10])
            second_half = np.mean(defect_counts[10:])
            if second_half > first_half * 1.5:
                anomalies.append({"type": "defect_rate_increase", "desc": "Defect rate increasing"})

        if anomalies:
            self.log(f"SPC anomalies detected: {anomalies}", 30)
            return {"anomalies": anomalies, "timestamp": time.time()}
        return None

    def get_quality_stats(self) -> Dict[str, Any]:
        """Get statistical summary of quality data.

        Returns:
            Dict with mean, std, trend, and defect distribution.
        """
        scores = self.spc_data["scores"]
        if not scores:
            return {
                "total_samples": 0,
                "mean_score": 0.0,
                "std_score": 0.0,
                "pass_rate": 0.0,
                "defect_distribution": {},
            }

        arr = np.array(scores)
        total = len(self.inspection_history)
        passed = sum(1 for s in self.inspection_history if s.get("decision") == "accept")

        return {
            "total_samples": len(scores),
            "mean_score": round(float(np.mean(arr)), 1),
            "std_score": round(float(np.std(arr)), 1),
            "min_score": round(float(np.min(arr)), 1),
            "max_score": round(float(np.max(arr)), 1),
            "pass_rate": round(passed / total, 3) if total > 0 else 0.0,
            "pass_count": passed,
            "fail_count": total - passed,
            "defect_distribution": dict(self.defect_counts),
            "trend": self._compute_trend(scores),
        }

    def _compute_trend(self, scores: List[float], window: int = 20) -> str:
        """Compute the quality trend from recent scores.

        Args:
            scores: List of quality scores.
            window: Window size for trend analysis.

        Returns:
            Trend string: 'improving', 'stable', 'declining'.
        """
        if len(scores) < window:
            return "insufficient_data"

        recent = scores[-window:]
        mid = len(recent) // 2
        first_half_mean = np.mean(recent[:mid])
        second_half_mean = np.mean(recent[mid:])

        diff = second_half_mean - first_half_mean
        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        else:
            return "stable"

    def get_defect_summary(self) -> Dict[str, Any]:
        """Get a summary of all defects found.

        Returns:
            Dict with defect counts and severity distribution.
        """
        severity_counts = {"minor": 0, "moderate": 0, "severe": 0}
        for entry in self.inspection_history:
            for defect in entry.get("defects", []):
                sev = defect.get("severity", "minor")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_defects": sum(self.defect_counts.values()),
            "by_type": dict(self.defect_counts),
            "by_severity": severity_counts,
        }

    def set_product_thresholds(self, product_type: str, thresholds: Dict[str, float]) -> None:
        """Set quality thresholds for a specific product type.

        Args:
            product_type: Product type identifier.
            thresholds: Dict with threshold values.
        """
        self.quality_thresholds[product_type] = thresholds
        self.log(f"Updated thresholds for '{product_type}': {thresholds}")

    def reset_statistics(self) -> None:
        """Reset all quality statistics."""
        self.inspection_history.clear()
        self.spc_data["scores"].clear()
        self.spc_data["defect_counts"].clear()
        self.defect_counts = {d.value: 0 for d in DefectType}
        self.log("Quality statistics reset")