#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
compat_dir="${skills_root}/envs/cuda-compat-12-9/usr/local/cuda-12.9/compat"
nvjitlink_dir="${skills_root}/envs/deepseekv4-vllm/lib/python3.10/site-packages/nvidia/nvjitlink/lib"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_server.sh"

if [[ ! -f "${compat_dir}/libcuda.so.575.57.08" ]]; then
  echo "CUDA 12.9 compatibility library is missing: ${compat_dir}" >&2
  exit 2
fi

export LD_LIBRARY_PATH="${compat_dir}:${nvjitlink_dir}:${LD_LIBRARY_PATH:-}"
export TORCHINDUCTOR_CACHE_DIR="${skills_root}/cache/torchinductor-deepseekv4"

exec "${server_script}"
