#!/usr/bin/env python3
"""Run SABER Judge v10 against the local DeepSeek V4 Flash API."""

from __future__ import annotations

from pathlib import Path
import sys

SKILLS_ROOT = Path("/2024233123/skills")
SABER_ROOT = SKILLS_ROOT / "projects/skill/saber"
OUTPUT_ROOT = SABER_ROOT / "judged_deepseek_v4_flash_v10_protocol"
JUDGE_MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
BASE_URL = "http://127.0.0.1:18020"

sys.path.insert(0, str(SKILLS_ROOT / "bin"))
import run_saber_parallel_judge as runner  # noqa: E402


def local_judged_path(
    model_slug: str, scenario: str, category: str, task_id: str
) -> Path:
    return OUTPUT_ROOT / model_slug / scenario / category / f"{task_id}.json"


# Keep every v10 result outside historical judged roots.  The shared client uses
# httpx.Client(trust_env=False), persists response/request metadata, and expands a
# length-truncated response only within this explicit context budget.
runner.JUDGE_MODEL = JUDGE_MODEL
runner.judge.JUDGED_DIR = OUTPUT_ROOT
runner.judge.JUDGE_CFG = {
    "id": JUDGE_MODEL,
    "type": "openai",
    "key": "local-judge",
    "base_url": BASE_URL,
    "context_window": 65536,
    "context_margin_tokens": 2048,
    "max_output_tokens": 6144,
    "max_output_tokens_ceiling": 12288,
    "max_length_retries": 1,
    "timeout_seconds": 600,
}
runner.judge.DEFAULT_BASE_URL = BASE_URL
runner.judge.judged_path = local_judged_path


if __name__ == "__main__":
    runner.main()
