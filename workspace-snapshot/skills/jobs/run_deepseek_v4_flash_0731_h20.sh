#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
vllm_env="${skills_root}/envs/deepseekv4-vllm"
cuda_home="${skills_root}/envs/cuda-toolkit-12-9/usr/local/cuda-12.9"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_final.sh"

export PATH="${vllm_env}/bin:${PATH}"
export LD_LIBRARY_PATH="${cuda_home}/lib64:${LD_LIBRARY_PATH:-}"
export FLASHINFER_WORKSPACE_BASE="${skills_root}/cache/flashinfer-deepseekv4"

exec "${server_script}"
