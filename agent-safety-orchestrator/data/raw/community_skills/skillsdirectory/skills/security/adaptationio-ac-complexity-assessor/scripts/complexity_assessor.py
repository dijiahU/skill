"""
AC Complexity Assessor - Assess feature and project complexity.

Analyzes features and projects to determine complexity levels,
estimate effort, and select appropriate processing pipelines.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class PipelineType(Enum):
    """Types of processing pipelines."""
    SIMPLE = "SIMPLE"      # 3 phases: Plan → Implement → Verify
    STANDARD = "STANDARD"  # 7 phases: Full TDD cycle
    COMPLEX = "COMPLEX"    # 8+ phases: Architecture-first


@dataclass
class ComplexityMetrics:
    """Metrics for complexity assessment."""
    total_features: int = 0
    dependency_depth: int = 0
    category_count: int = 0
    integration_points: int = 0
    technology_complexity: int = 1
    external_services: int = 0
    security_requirements: int = 0


@dataclass
class FeatureEstimate:
    """Effort estimate for a single feature."""
    id: str
    complexity: str  # low, medium, high
    estimated_hours: float = 1.0
    factors: List[str] = field(default_factory=list)
    risk_level: str = "low"


@dataclass
class ProjectEstimates:
    """Overall project estimates."""
    total_hours: float = 0.0
    estimated_cost_usd: float = 0.0
    estimated_sessions: int = 0
    features_per_session: float = 0.0
    completion_days: int = 0


@dataclass
class AssessmentResult:
    """Complete complexity assessment."""
    project_complexity: str
    pipeline_type: PipelineType
    metrics: ComplexityMetrics
    estimates: ProjectEstimates
    feature_estimates: List[FeatureEstimate] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)


# Complexity indicators
COMPLEXITY_INDICATORS = {
    "high": [
        "oauth", "payment", "real-time", "websocket", "machine learning",
        "ai", "encryption", "distributed", "microservice", "kubernetes",
        "blockchain", "streaming", "video", "audio"
    ],
    "medium": [
        "api", "database", "authentication", "migration", "integration",
        "cache", "queue", "background", "notification", "email",
        "upload", "search", "filter", "pagination"
    ],
    "low": [
        "ui", "form", "button", "display", "list", "view",
        "component", "style", "layout", "text", "label"
    ]
}

# Cost constants (USD per 1M tokens, approximate)
COST_PER_MILLION_TOKENS = 15.0  # Opus 4.5 pricing
TOKENS_PER_FEATURE_AVG = 50000


class ComplexityAssessor:
    """
    Assess complexity for effort estimation and planning.

    Usage:
        assessor = ComplexityAssessor(project_dir)
        assessment = await assessor.assess_project()
    """

    FEATURE_LIST_FILE = "feature_list.json"

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._features: List[Dict[str, Any]] = []

    async def assess_project(self) -> AssessmentResult:
        """
        Assess overall project complexity.

        Returns:
            Complete AssessmentResult
        """
        await self._load_features()

        if not self._features:
            return AssessmentResult(
                project_complexity="UNKNOWN",
                pipeline_type=PipelineType.SIMPLE,
                metrics=ComplexityMetrics(),
                estimates=ProjectEstimates()
            )

        # Calculate metrics
        metrics = self._calculate_metrics()

        # Determine complexity level
        project_complexity = self._determine_complexity(metrics)

        # Select pipeline
        pipeline_type = self._select_pipeline(project_complexity, metrics)

        # Generate feature estimates
        feature_estimates = self._estimate_features()

        # Calculate project estimates
        estimates = self._calculate_project_estimates(feature_estimates, metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, project_complexity)

        # Identify risks
        risk_factors = self._identify_risks(metrics, feature_estimates)

        return AssessmentResult(
            project_complexity=project_complexity,
            pipeline_type=pipeline_type,
            metrics=metrics,
            estimates=estimates,
            feature_estimates=feature_estimates,
            recommendations=recommendations,
            risk_factors=risk_factors
        )

    async def assess_feature(self, feature_id: str) -> FeatureEstimate:
        """Assess a single feature's complexity."""
        await self._load_features()

        for feature in self._features:
            if feature["id"] == feature_id:
                return self._estimate_single_feature(feature)

        return FeatureEstimate(
            id=feature_id,
            complexity="unknown",
            estimated_hours=0,
            factors=["Feature not found"]
        )

    async def recommend_parallelization(self) -> List[List[str]]:
        """Recommend features that can be parallelized."""
        await self._load_features()

        # Group by category
        by_category: Dict[str, List[str]] = {}
        for feature in self._features:
            if feature.get("passes"):
                continue

            category = feature.get("category", "general")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(feature["id"])

        # Return groups of 2+ that share no dependencies
        parallel_groups = []
        for category, feature_ids in by_category.items():
            if len(feature_ids) >= 2:
                # Check for no interdependencies
                independent = self._find_independent_features(feature_ids)
                if len(independent) >= 2:
                    parallel_groups.append(independent)

        return parallel_groups

    def _calculate_metrics(self) -> ComplexityMetrics:
        """Calculate complexity metrics."""
        metrics = ComplexityMetrics()

        metrics.total_features = len(self._features)

        # Calculate dependency depth
        metrics.dependency_depth = self._calculate_dependency_depth()

        # Count categories
        categories = set(f.get("category", "general") for f in self._features)
        metrics.category_count = len(categories)

        # Count integration points
        integration_keywords = ["api", "integrate", "connect", "external", "service"]
        for feature in self._features:
            desc = feature.get("description", "").lower()
            if any(kw in desc for kw in integration_keywords):
                metrics.integration_points += 1

        # Technology complexity (estimate from descriptions)
        tech_keywords = ["oauth", "websocket", "graphql", "kubernetes", "docker"]
        for feature in self._features:
            desc = feature.get("description", "").lower()
            if any(kw in desc for kw in tech_keywords):
                metrics.technology_complexity += 1

        # Security requirements
        security_keywords = ["security", "auth", "permission", "encrypt", "token"]
        for feature in self._features:
            desc = feature.get("description", "").lower()
            if any(kw in desc for kw in security_keywords):
                metrics.security_requirements += 1

        return metrics

    def _calculate_dependency_depth(self) -> int:
        """Calculate maximum dependency chain depth."""
        max_depth = 0

        def get_depth(feature_id: str, visited: set) -> int:
            if feature_id in visited:
                return 0  # Cycle

            feature = next((f for f in self._features if f["id"] == feature_id), None)
            if not feature:
                return 0

            visited.add(feature_id)
            deps = feature.get("dependencies", [])

            if not deps:
                return 1

            return 1 + max(get_depth(dep, visited.copy()) for dep in deps)

        for feature in self._features:
            depth = get_depth(feature["id"], set())
            max_depth = max(max_depth, depth)

        return max_depth

    def _determine_complexity(self, metrics: ComplexityMetrics) -> str:
        """Determine overall project complexity."""
        score = 0

        # Feature count scoring
        if metrics.total_features > 100:
            score += 3
        elif metrics.total_features > 50:
            score += 2
        elif metrics.total_features > 20:
            score += 1

        # Dependency depth scoring
        if metrics.dependency_depth > 5:
            score += 3
        elif metrics.dependency_depth > 3:
            score += 2
        elif metrics.dependency_depth > 1:
            score += 1

        # Integration scoring
        if metrics.integration_points > 5:
            score += 2
        elif metrics.integration_points > 2:
            score += 1

        # Technology complexity
        if metrics.technology_complexity > 5:
            score += 2
        elif metrics.technology_complexity > 2:
            score += 1

        # Determine level
        if score >= 8:
            return "COMPLEX"
        elif score >= 4:
            return "STANDARD"
        else:
            return "SIMPLE"

    def _select_pipeline(
        self,
        complexity: str,
        metrics: ComplexityMetrics
    ) -> PipelineType:
        """Select appropriate processing pipeline."""
        if complexity == "COMPLEX":
            return PipelineType.COMPLEX
        elif complexity == "STANDARD":
            return PipelineType.STANDARD
        else:
            return PipelineType.SIMPLE

    def _estimate_features(self) -> List[FeatureEstimate]:
        """Estimate all features."""
        return [self._estimate_single_feature(f) for f in self._features]

    def _estimate_single_feature(self, feature: Dict[str, Any]) -> FeatureEstimate:
        """Estimate a single feature."""
        desc = feature.get("description", "").lower()
        factors = []

        # Base complexity from keywords
        complexity = "low"
        hours = 1.0

        for level, keywords in COMPLEXITY_INDICATORS.items():
            if any(kw in desc for kw in keywords):
                complexity = level
                break

        # Adjust hours based on complexity
        if complexity == "high":
            hours = 4.0
        elif complexity == "medium":
            hours = 2.0

        # Factor in dependencies
        deps = feature.get("dependencies", [])
        if len(deps) > 2:
            hours *= 1.2
            factors.append("multiple_dependencies")

        # Factor in test cases
        test_cases = feature.get("test_cases", [])
        if len(test_cases) > 3:
            hours *= 1.1
            factors.append("extensive_testing")

        # Risk assessment
        risk = "low"
        if complexity == "high" or len(deps) > 3:
            risk = "medium"
        if "external" in desc or "third-party" in desc:
            risk = "high"
            factors.append("external_dependency")

        return FeatureEstimate(
            id=feature["id"],
            complexity=complexity,
            estimated_hours=round(hours, 1),
            factors=factors,
            risk_level=risk
        )

    def _calculate_project_estimates(
        self,
        feature_estimates: List[FeatureEstimate],
        metrics: ComplexityMetrics
    ) -> ProjectEstimates:
        """Calculate overall project estimates."""
        total_hours = sum(fe.estimated_hours for fe in feature_estimates)

        # Token cost estimate
        tokens = metrics.total_features * TOKENS_PER_FEATURE_AVG
        cost = (tokens / 1_000_000) * COST_PER_MILLION_TOKENS

        # Session estimate (assuming 5 features per session average)
        features_per_session = 5
        estimated_sessions = max(1, metrics.total_features // features_per_session)

        # Days estimate (assuming 8 productive hours per day)
        completion_days = max(1, int(total_hours / 8))

        return ProjectEstimates(
            total_hours=round(total_hours, 1),
            estimated_cost_usd=round(cost, 2),
            estimated_sessions=estimated_sessions,
            features_per_session=features_per_session,
            completion_days=completion_days
        )

    def _generate_recommendations(
        self,
        metrics: ComplexityMetrics,
        complexity: str
    ) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []

        if metrics.dependency_depth > 4:
            recommendations.append(
                "Consider breaking deep dependency chains into smaller modules"
            )

        if metrics.integration_points > 5:
            recommendations.append(
                "Create integration abstraction layer to manage external services"
            )

        if metrics.total_features > 50:
            recommendations.append(
                "Consider implementing features in phases/milestones"
            )

        if complexity == "COMPLEX":
            recommendations.append(
                "Recommend architecture review before implementation"
            )

        if metrics.security_requirements > 3:
            recommendations.append(
                "Schedule security review after core features complete"
            )

        return recommendations

    def _identify_risks(
        self,
        metrics: ComplexityMetrics,
        estimates: List[FeatureEstimate]
    ) -> List[str]:
        """Identify project risks."""
        risks = []

        high_risk_features = [e for e in estimates if e.risk_level == "high"]
        if high_risk_features:
            risk_ids = [f.id for f in high_risk_features[:3]]
            risks.append(f"High-risk features: {', '.join(risk_ids)}")

        if metrics.dependency_depth > 5:
            risks.append("Deep dependency chains may cause cascading delays")

        if metrics.integration_points > 3:
            risks.append("Multiple integrations increase external failure points")

        return risks

    def _find_independent_features(self, feature_ids: List[str]) -> List[str]:
        """Find features with no interdependencies."""
        features = [f for f in self._features if f["id"] in feature_ids]

        independent = []
        for feature in features:
            deps = set(feature.get("dependencies", []))
            # Check if no deps overlap with other features in group
            if not deps & set(feature_ids):
                independent.append(feature["id"])

        return independent

    async def _load_features(self) -> None:
        """Load features from file."""
        path = self.project_dir / self.FEATURE_LIST_FILE

        if not path.exists():
            self._features = []
            return

        with open(path) as f:
            data = json.load(f)

        self._features = data.get("features", [])


# Convenience function
async def assess_complexity(project_dir: Path) -> AssessmentResult:
    """Assess project complexity."""
    assessor = ComplexityAssessor(project_dir)
    return await assessor.assess_project()
