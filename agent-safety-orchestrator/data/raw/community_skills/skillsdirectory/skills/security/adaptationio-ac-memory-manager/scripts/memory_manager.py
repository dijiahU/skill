"""
AC Memory Manager - Manage persistent memory for autonomous coding.

Integrates with Graphiti memory system for cross-session knowledge storage.
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    key: str
    value: Any
    memory_type: str  # episodic, semantic, procedural
    created_at: str
    accessed_at: str
    access_count: int = 0
    relevance_score: float = 1.0


@dataclass
class MemoryConfig:
    """Memory manager configuration."""
    enabled: bool = True
    memory_dir: str = ".claude/memory"
    max_entries: int = 1000
    use_graphiti: bool = False  # Enable when Graphiti available


class MemoryManager:
    """
    Manage persistent memory for autonomous coding.

    Usage:
        memory = MemoryManager(project_dir)
        await memory.store("auth patterns", {"jwt": True})
    """

    def __init__(
        self,
        project_dir: Path,
        config: Optional[MemoryConfig] = None
    ):
        self.project_dir = Path(project_dir)
        self.config = config or MemoryConfig()
        self._memory: Dict[str, MemoryEntry] = {}

    async def initialize(self) -> None:
        """Initialize memory system."""
        memory_dir = self.project_dir / self.config.memory_dir
        memory_dir.mkdir(parents=True, exist_ok=True)
        await self._load_memory()

    async def store(
        self,
        key: str,
        value: Any,
        memory_type: str = "semantic"
    ) -> MemoryEntry:
        """Store a memory entry."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        entry_id = f"mem-{len(self._memory):06d}"

        entry = MemoryEntry(
            id=entry_id,
            key=key,
            value=value,
            memory_type=memory_type,
            created_at=timestamp,
            accessed_at=timestamp
        )

        self._memory[key] = entry
        await self._save_memory()

        return entry

    async def retrieve(
        self,
        query: str,
        memory_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Retrieve memories matching query."""
        results = []
        query_lower = query.lower()

        for key, entry in self._memory.items():
            if memory_type and entry.memory_type != memory_type:
                continue

            if query_lower in key.lower():
                entry.access_count += 1
                entry.accessed_at = datetime.utcnow().isoformat() + "Z"
                results.append(entry)

        await self._save_memory()
        return sorted(results, key=lambda e: e.relevance_score, reverse=True)

    async def get(self, key: str) -> Optional[Any]:
        """Get specific memory by key."""
        entry = self._memory.get(key)
        if entry:
            entry.access_count += 1
            entry.accessed_at = datetime.utcnow().isoformat() + "Z"
            await self._save_memory()
            return entry.value
        return None

    async def forget(self, key: str) -> bool:
        """Remove a memory entry."""
        if key in self._memory:
            del self._memory[key]
            await self._save_memory()
            return True
        return False

    async def get_all(self, memory_type: Optional[str] = None) -> List[MemoryEntry]:
        """Get all memories of a type."""
        if memory_type:
            return [e for e in self._memory.values() if e.memory_type == memory_type]
        return list(self._memory.values())

    async def _load_memory(self) -> None:
        """Load memory from disk."""
        memory_file = self.project_dir / self.config.memory_dir / "memories.json"

        if memory_file.exists():
            with open(memory_file) as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = MemoryEntry(**entry_data)
                self._memory[entry.key] = entry

    async def _save_memory(self) -> None:
        """Save memory to disk."""
        memory_file = self.project_dir / self.config.memory_dir / "memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "entries": [
                {
                    "id": e.id,
                    "key": e.key,
                    "value": e.value,
                    "memory_type": e.memory_type,
                    "created_at": e.created_at,
                    "accessed_at": e.accessed_at,
                    "access_count": e.access_count,
                    "relevance_score": e.relevance_score
                }
                for e in self._memory.values()
            ]
        }

        with open(memory_file, 'w') as f:
            json.dump(data, f, indent=2)
