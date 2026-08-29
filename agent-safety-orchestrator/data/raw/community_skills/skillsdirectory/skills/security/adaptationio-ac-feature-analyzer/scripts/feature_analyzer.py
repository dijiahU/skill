"""
AC Feature Analyzer - Analyze features and dependencies.

Analyzes feature relationships to determine optimal build order,
identify blockers, and calculate critical paths.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any
from collections import defaultdict


@dataclass
class DependencyGraph:
    """Dependency graph representation."""
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    reverse_edges: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class CategoryProgress:
    """Progress within a category."""
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    blocked: int = 0


@dataclass
class AnalysisResult:
    """Complete feature analysis result."""
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    critical_path: List[str] = field(default_factory=list)
    blockers: Dict[str, List[str]] = field(default_factory=dict)
    categories: Dict[str, CategoryProgress] = field(default_factory=dict)
    next_features: List[str] = field(default_factory=list)
    bottlenecks: List[str] = field(default_factory=list)
    parallel_opportunities: List[List[str]] = field(default_factory=list)
    circular_dependencies: List[List[str]] = field(default_factory=list)
    total_features: int = 0
    completed_features: int = 0
    completion_percentage: float = 0.0


class FeatureAnalyzer:
    """
    Analyze features, dependencies, and critical paths.

    Usage:
        analyzer = FeatureAnalyzer(project_dir)
        analysis = await analyzer.analyze()
    """

    FEATURE_LIST_FILE = "feature_list.json"

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._features: List[Dict[str, Any]] = []
        self._graph: Optional[DependencyGraph] = None

    async def analyze(self) -> AnalysisResult:
        """
        Perform complete feature analysis.

        Returns:
            AnalysisResult with all analysis data
        """
        await self._load_features()

        if not self._features:
            return AnalysisResult()

        # Build dependency graph
        self._graph = self._build_graph()

        # Run all analyses
        return AnalysisResult(
            dependency_graph=self._graph.edges,
            critical_path=self._find_critical_path(),
            blockers=self._find_blockers(),
            categories=self._analyze_categories(),
            next_features=self._find_next_features(),
            bottlenecks=self._find_bottlenecks(),
            parallel_opportunities=self._find_parallel_opportunities(),
            circular_dependencies=self._find_circular_dependencies(),
            total_features=len(self._features),
            completed_features=sum(1 for f in self._features if f.get("passes")),
            completion_percentage=self._calculate_completion()
        )

    async def get_next_feature(self) -> Optional[Dict[str, Any]]:
        """Get the next feature to work on."""
        await self._load_features()
        self._graph = self._build_graph()

        next_ids = self._find_next_features()
        if not next_ids:
            return None

        for feature in self._features:
            if feature["id"] == next_ids[0]:
                return feature

        return None

    async def get_blocked_features(self) -> List[Dict[str, Any]]:
        """Get all features that are currently blocked."""
        await self._load_features()
        self._graph = self._build_graph()

        blockers = self._find_blockers()
        blocked_ids = set(blockers.keys())

        return [f for f in self._features if f["id"] in blocked_ids]

    async def get_dependency_chain(self, feature_id: str) -> List[str]:
        """Get the dependency chain for a specific feature."""
        await self._load_features()
        self._graph = self._build_graph()

        return self._get_all_dependencies(feature_id)

    def _build_graph(self) -> DependencyGraph:
        """Build dependency graph from features."""
        graph = DependencyGraph()

        for feature in self._features:
            feature_id = feature["id"]
            graph.nodes.add(feature_id)
            graph.edges[feature_id] = feature.get("dependencies", [])

            # Build reverse edges
            for dep in feature.get("dependencies", []):
                if dep not in graph.reverse_edges:
                    graph.reverse_edges[dep] = []
                graph.reverse_edges[dep].append(feature_id)

        return graph

    def _find_critical_path(self) -> List[str]:
        """Find the critical path (longest dependency chain)."""
        if not self._graph:
            return []

        # Find features with no dependents (end nodes)
        end_nodes = [
            node for node in self._graph.nodes
            if node not in self._graph.reverse_edges
        ]

        longest_path = []
        for end_node in end_nodes:
            path = self._longest_path_to(end_node)
            if len(path) > len(longest_path):
                longest_path = path

        return longest_path

    def _longest_path_to(self, node: str, visited: Set[str] = None) -> List[str]:
        """Find longest path ending at node."""
        if visited is None:
            visited = set()

        if node in visited:
            return []

        visited.add(node)

        deps = self._graph.edges.get(node, [])
        if not deps:
            return [node]

        longest = []
        for dep in deps:
            path = self._longest_path_to(dep, visited.copy())
            if len(path) > len(longest):
                longest = path

        return longest + [node]

    def _find_blockers(self) -> Dict[str, List[str]]:
        """Find which features are blocked and by what."""
        blockers = {}
        completed_ids = {f["id"] for f in self._features if f.get("passes")}

        for feature in self._features:
            if feature.get("passes"):
                continue

            unmet_deps = [
                dep for dep in feature.get("dependencies", [])
                if dep not in completed_ids
            ]

            if unmet_deps:
                blockers[feature["id"]] = unmet_deps

        return blockers

    def _analyze_categories(self) -> Dict[str, CategoryProgress]:
        """Analyze progress by category."""
        categories = defaultdict(lambda: CategoryProgress())

        for feature in self._features:
            category = feature.get("category", "general")
            categories[category].total += 1

            if feature.get("passes"):
                categories[category].completed += 1
            elif feature.get("status") == "in_progress":
                categories[category].in_progress += 1
            elif feature.get("status") == "blocked":
                categories[category].blocked += 1

        return dict(categories)

    def _find_next_features(self) -> List[str]:
        """Find features ready to be worked on."""
        completed_ids = {f["id"] for f in self._features if f.get("passes")}
        in_progress = {f["id"] for f in self._features if f.get("status") == "in_progress"}

        ready = []
        for feature in self._features:
            if feature.get("passes"):
                continue
            if feature["id"] in in_progress:
                continue

            # Check dependencies met
            deps_met = all(
                dep in completed_ids
                for dep in feature.get("dependencies", [])
            )

            if deps_met:
                ready.append(feature["id"])

        # Sort by priority
        ready.sort(key=lambda fid: next(
            (f.get("priority", 5) for f in self._features if f["id"] == fid),
            5
        ))

        return ready[:5]  # Return top 5

    def _find_bottlenecks(self) -> List[str]:
        """Find features that block the most other features."""
        if not self._graph:
            return []

        # Count dependents for each feature
        dependent_counts = {}
        for node in self._graph.nodes:
            dependent_counts[node] = len(self._graph.reverse_edges.get(node, []))

        # Filter to incomplete features
        completed_ids = {f["id"] for f in self._features if f.get("passes")}
        bottlenecks = [
            (node, count) for node, count in dependent_counts.items()
            if count > 0 and node not in completed_ids
        ]

        # Sort by dependent count
        bottlenecks.sort(key=lambda x: x[1], reverse=True)

        return [node for node, _ in bottlenecks[:5]]

    def _find_parallel_opportunities(self) -> List[List[str]]:
        """Find features that can be worked on in parallel."""
        completed_ids = {f["id"] for f in self._features if f.get("passes")}

        # Group ready features by category
        ready_by_category = defaultdict(list)
        for feature in self._features:
            if feature.get("passes"):
                continue

            deps_met = all(
                dep in completed_ids
                for dep in feature.get("dependencies", [])
            )

            if deps_met:
                category = feature.get("category", "general")
                ready_by_category[category].append(feature["id"])

        # Return groups of 3+ parallel opportunities
        return [
            ids for ids in ready_by_category.values()
            if len(ids) >= 2
        ]

    def _find_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies."""
        if not self._graph:
            return []

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self._graph.edges.get(node, []):
                if dep not in visited:
                    dfs(dep, path.copy())
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])

            rec_stack.remove(node)

        for node in self._graph.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def _get_all_dependencies(self, feature_id: str) -> List[str]:
        """Get all transitive dependencies for a feature."""
        if not self._graph:
            return []

        all_deps = []
        to_process = list(self._graph.edges.get(feature_id, []))
        processed = set()

        while to_process:
            dep = to_process.pop(0)
            if dep in processed:
                continue

            processed.add(dep)
            all_deps.append(dep)
            to_process.extend(self._graph.edges.get(dep, []))

        return all_deps

    def _calculate_completion(self) -> float:
        """Calculate completion percentage."""
        if not self._features:
            return 0.0

        completed = sum(1 for f in self._features if f.get("passes"))
        return round(completed / len(self._features) * 100, 1)

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
async def analyze_features(project_dir: Path) -> AnalysisResult:
    """Analyze features in a project."""
    analyzer = FeatureAnalyzer(project_dir)
    return await analyzer.analyze()
