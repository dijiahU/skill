#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
vllm_env="${skills_root}/envs/deepseekv4-vllm"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_final.sh"

export PATH="${vllm_env}/bin:${PATH}"

exec "${server_script}"
