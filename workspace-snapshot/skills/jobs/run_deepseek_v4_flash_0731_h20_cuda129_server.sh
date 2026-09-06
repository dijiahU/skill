#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
cuda_home="${skills_root}/envs/cuda-toolkit-12-9/usr/local/cuda-12.9"
compat_server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_compat_server.sh"

if [[ ! -x "${cuda_home}/bin/nvcc" ]]; then
  echo "CUDA 12.9 NVCC is missing: ${cuda_home}/bin/nvcc" >&2
  exit 2
fi

export CUDA_HOME="${cuda_home}"
export CUDACXX="${cuda_home}/bin/nvcc"
export PATH="${cuda_home}/bin:${PATH}"
export CPATH="${cuda_home}/include:${CPATH:-}"
export LIBRARY_PATH="${cuda_home}/lib64:${LIBRARY_PATH:-}"

exec "${compat_server_script}"
