"""Historical full-treatment service settings for the v9 rerun controller.

Importing this module only constructs data; it never starts services or reads
provider credentials. GPU numbers refer to physical GPUs. The controller must
reserve ``gpus`` for the entire service-and-worker lifecycle, merge each service
``env`` into its own environment, and create fresh logs/results for this run.
"""

from __future__ import annotations

import os
from pathlib import Path


SKILLS_ROOT = Path("/2024233123/skills")
SABER_ROOT = SKILLS_ROOT / "projects/skill/saber"
MODEL_ROOT = SKILLS_ROOT / "models/modelscope"
QWEN_ENV = SKILLS_ROOT / "envs/qwen35-vllm"
DEEPSEEK_ENV = SKILLS_ROOT / "envs/deepseekv4-vllm"
CUDA_ROOT = SKILLS_ROOT / "envs/cuda-toolkit-12-9/usr/local/cuda-12.9"
CUDA_COMPAT = SKILLS_ROOT / "envs/cuda-compat-12-9/usr/local/cuda-12.9/compat"
API_HOST = "172.24.29.43"


def _prepend(variable: str, *paths: Path) -> str:
    """Preserve an inherited search path without adding an empty cwd entry."""
    values = [str(path) for path in paths]
    inherited = os.environ.get(variable, "")
    if inherited:
        values.append(inherited)
    return ":".join(values)


def _endpoint(port: int, workers: range, config_key: int = 0) -> dict:
    return {
        "config_key": config_key,
        "base_url": f"http://{API_HOST}:{port}/v1",
        "worker_indices": list(workers),
    }


def _vllm_service(
    name: str,
    environment: Path,
    model: str,
    port: int,
    arguments: list[str],
    env: dict[str, str],
    ready_timeout: int,
) -> dict:
    return {
        "name": name,
        "argv": [
            str(environment / "bin/vllm"),
            "serve",
            str(MODEL_ROOT / model),
            "--served-model-name", model,
            "--host", "0.0.0.0",
            "--port", str(port),
            *arguments,
        ],
        "env": env,
        "health_url": f"http://127.0.0.1:{port}/health",
        "ready_timeout": ready_timeout,
    }


def _proxy_service(
    name: str, script: str, port: int, upstream_port: int,
    arguments: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "argv": [
            str(QWEN_ENV / "bin/python"),
            str(SKILLS_ROOT / "bin" / script),
            "--host", "0.0.0.0",
            "--port", str(port),
            "--upstream", f"http://127.0.0.1:{upstream_port}",
            *(arguments or []),
        ],
        "env": {},
        "health_url": f"http://127.0.0.1:{port}/v1/models",
        "ready_timeout": 60,
    }


def _cuda129_env(cache_suffix: str) -> dict[str, str]:
    return {
        "CUDA_VISIBLE_DEVICES": "0,1",
        "CUDA_HOME": str(CUDA_ROOT),
        "CUDACXX": str(CUDA_ROOT / "bin/nvcc"),
        "PATH": _prepend("PATH", DEEPSEEK_ENV / "bin", CUDA_ROOT / "bin"),
        "CPATH": _prepend("CPATH", CUDA_ROOT / "include"),
        "LIBRARY_PATH": _prepend("LIBRARY_PATH", CUDA_ROOT / "lib64"),
        "LD_LIBRARY_PATH": _prepend(
            "LD_LIBRARY_PATH", CUDA_COMPAT,
            DEEPSEEK_ENV / "lib/python3.10/site-packages/nvidia/nvjitlink/lib",
            CUDA_ROOT / "lib64",
        ),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "VLLM_NO_USAGE_STATS": "1",
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "FLASHINFER_WORKSPACE_BASE": str(SKILLS_ROOT / f"cache/flashinfer-{cache_suffix}"),
        "VLLM_CACHE_ROOT": str(SKILLS_ROOT / f"cache/vllm-{cache_suffix}"),
        "TORCHINDUCTOR_CACHE_DIR": str(SKILLS_ROOT / f"cache/torchinductor-{cache_suffix}"),
        "OMP_NUM_THREADS": "8",
    }


def _qwen_service(gpu: int, port: int) -> dict:
    return _vllm_service(
        f"qwen-vllm-gpu{gpu}", QWEN_ENV, "Qwen/Qwen3.8-27B-FP8", port,
        [
            "--tensor-parallel-size", "1",
            "--max-model-len", "32768",
            "--max-num-seqs", "4",
            "--gpu-memory-utilization", "0.80",
            "--enable-auto-tool-choice",
            "--tool-call-parser", "qwen3_xml",
            "--reasoning-parser", "qwen3",
            "--language-model-only",
        ],
        {
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "PATH": _prepend("PATH", QWEN_ENV / "bin"),
            "SAFETENSORS_FAST_GPU": "1",
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
            "VLLM_NO_USAGE_STATS": "1",
            "VLLM_FORCE_NATIVE_GDN": "1",
        },
        900,
    )


MODEL_SPECS: list[dict] = [
    {
        "key": "mistral",
        "label": "Mistral-Small-4-119B-2603",
        "old_config": str(SKILLS_ROOT / "jobs/saber_mistral_small4_119b_treatment_716.json"),
        "old_slug": "codex_mistral_small4_119b_treatment_716",
        "gpus": [0, 1],
        "workers": 8,
        "endpoints": [_endpoint(18030, range(8))],
        "services": [
            _vllm_service(
                "mistral-vllm", DEEPSEEK_ENV, "mistralai/Mistral-Small-4-119B-2603", 18030,
                [
                    "--trust-remote-code",
                    "--tokenizer-mode", "mistral",
                    "--config-format", "mistral",
                    "--load-format", "mistral",
                    "--tensor-parallel-size", "2",
                    "--dtype", "bfloat16",
                    "--max-model-len", "32768",
                    "--max-num-seqs", "8",
                    "--max-num-batched-tokens", "8192",
                    "--gpu-memory-utilization", "0.90",
                    "--attention-backend", "FLASH_ATTN_MLA",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser", "mistral",
                    "--reasoning-parser", "mistral",
                    "--language-model-only",
                ],
                {
                    **_cuda129_env("mistral-small4"),
                    "PYTHONPATH": _prepend("PYTHONPATH", SKILLS_ROOT / "compat/mistral_developer_role"),
                    "SABER_MISTRAL_DEVELOPER_ROLE_COMPAT": "1",
                },
                3000,
            ),
        ],
    },
    {
        "key": "minimax",
        "label": "MiniMax-M2.5",
        "old_config": str(SKILLS_ROOT / "jobs/saber_minimax_m25_treatment_716.json"),
        "old_slug": "codex_minimax_m25_treatment_716",
        "gpus": [0, 1],
        "workers": 8,
        "endpoints": [_endpoint(18007, range(8))],
        "services": [
            _vllm_service(
                "minimax-vllm", QWEN_ENV, "MiniMax/MiniMax-M2.5", 18006,
                [
                    "--trust-remote-code",
                    "--tensor-parallel-size", "2",
                    "--max-model-len", "32768",
                    "--max-num-seqs", "4",
                    "--gpu-memory-utilization", "0.90",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser", "minimax_m2",
                    "--reasoning-parser", "minimax_m2_append_think",
                    "--compilation-config", '{"cudagraph_mode":"PIECEWISE"}',
                    "--language-model-only",
                ],
                {
                    "CUDA_VISIBLE_DEVICES": "0,1",
                    "PATH": _prepend("PATH", QWEN_ENV / "bin"),
                    "SAFETENSORS_FAST_GPU": "1",
                    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
                    "VLLM_NO_USAGE_STATS": "1",
                },
                1200,
            ),
            _proxy_service(
                "minimax-proxy", "vllm_responses_compat_proxy.py", 18007, 18006,
                ["--emulate-stream", "--temperature", "0"],
            ),
        ],
    },
    {
        "key": "deepseek_flash",
        "label": "DeepSeek-V4-Flash-0731",
        "old_config": str(SKILLS_ROOT / "jobs/saber_deepseek_v4_flash_local_treatment_716.json"),
        "old_slug": "codex_deepseek_v4_flash_local_treatment_716",
        "gpus": [0, 1],
        "workers": 8,
        "endpoints": [_endpoint(18020, range(8))],
        "services": [
            _vllm_service(
                "deepseek-flash-vllm", DEEPSEEK_ENV, "deepseek-ai/DeepSeek-V4-Flash-0731", 18020,
                [
                    "--api-server-count", "1",
                    "--trust-remote-code",
                    "--tokenizer-mode", "deepseek_v4",
                    "--data-parallel-size", "2",
                    "--enable-expert-parallel",
                    "--moe-backend", "auto",
                    "--kv-cache-dtype", "fp8",
                    "--block-size", "256",
                    "--max-model-len", "65536",
                    "--max-num-seqs", "4",
                    "--max-num-batched-tokens", "8192",
                    "--gpu-memory-utilization", "0.90",
                    "--enforce-eager",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser", "deepseek_v4",
                    "--reasoning-parser", "deepseek_v4",
                ],
                {**_cuda129_env("deepseekv4"), "VLLM_ENGINE_READY_TIMEOUT_S": "1800"},
                1800,
            ),
        ],
    },
    {
        "key": "qwen",
        "label": "Qwen3.8-27B-FP8",
        "old_config": str(SKILLS_ROOT / "jobs/saber_qwen38_27b_treatment_716.json"),
        "old_slug": "codex_qwen38_27b_treatment_716",
        "gpus": [0, 1],
        "workers": 8,
        "endpoints": [_endpoint(18011, range(4), 0), _endpoint(18013, range(4, 8), 1)],
        "services": [
            _qwen_service(0, 18010),
            _qwen_service(1, 18012),
            _proxy_service(
                "qwen-proxy-gpu0", "vllm_responses_compat_proxy.py", 18011, 18010,
                ["--emulate-stream", "--temperature", "0"],
            ),
            _proxy_service(
                "qwen-proxy-gpu1", "vllm_responses_compat_proxy.py", 18013, 18012,
                ["--emulate-stream", "--temperature", "0"],
            ),
        ],
    },
    {
        "key": "glm",
        "label": "GLM-4.7-Flash",
        "old_config": str(SKILLS_ROOT / "jobs/saber_glm47_treatment_716.json"),
        "old_slug": "codex_glm47_flash_treatment_716",
        "gpus": [1],
        "workers": 8,
        "endpoints": [_endpoint(18003, range(8))],
        "services": [
            _vllm_service(
                "glm-vllm", QWEN_ENV, "ZhipuAI/GLM-4.7-Flash", 18002,
                [
                    "--tensor-parallel-size", "1",
                    "--dtype", "bfloat16",
                    "--max-model-len", "32768",
                    "--max-num-seqs", "8",
                    "--gpu-memory-utilization", "0.80",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser", "glm47",
                    "--reasoning-parser", "glm45",
                    "--language-model-only",
                ],
                {
                    "CUDA_VISIBLE_DEVICES": "1",
                    "PYTHONPATH": str(SKILLS_ROOT / "envs/glm47-transformers-main"),
                    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
                    "VLLM_USE_EXPERIMENTAL_PARSER_CONTEXT": "1",
                },
                900,
            ),
            _proxy_service("glm-proxy", "vllm_responses_compat_proxy_glm47.py", 18003, 18002),
        ],
    },
    {
        "key": "gptoss",
        "label": "gpt-oss-120b",
        "old_config": str(SKILLS_ROOT / "jobs/saber_gptoss120b_treatment_716.json"),
        "old_slug": "codex_gptoss120b_treatment_716",
        "gpus": [0],
        "workers": 8,
        "endpoints": [_endpoint(18005, range(8))],
        "services": [
            _vllm_service(
                "gptoss-vllm", QWEN_ENV, "OpenAI-Mirror/gpt-oss-120b", 18004,
                [
                    "--tensor-parallel-size", "1",
                    "--max-model-len", "32768",
                    "--max-num-seqs", "8",
                    "--gpu-memory-utilization", "0.85",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser", "openai",
                    "--language-model-only",
                ],
                {
                    "CUDA_VISIBLE_DEVICES": "0",
                    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
                    "VLLM_NO_USAGE_STATS": "1",
                },
                900,
            ),
            _proxy_service("gptoss-proxy", "vllm_responses_compat_proxy_gptoss.py", 18005, 18004),
        ],
    },
    {
        "key": "deepseek_pro",
        "label": "DeepSeek V4 Pro",
        "old_config": str(SABER_ROOT / "config.json"),
        "old_slug": "codex_deepseek_v4_pro",
        "provider_credentials_path": str(
            SKILLS_ROOT / "projects/skill/openagentsafety/.llm_config/deepseek-v4-pro.json"
        ),
        "gpus": [],
        "workers": 8,
        "endpoints": [{
            "config_key": 0,
            "base_url": "https://api.deepseek.com",
            "worker_indices": list(range(8)),
        }],
        "services": [],
    },
]
