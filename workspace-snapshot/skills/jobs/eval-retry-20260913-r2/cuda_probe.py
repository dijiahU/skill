"""Check matching cuBLAS libraries and the H20 BF16 logit operation."""
import json
import os
from pathlib import Path
import sys
import torch

assert os.environ.get('CUDA_VISIBLE_DEVICES') in ['0', '1']
paths = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if 'libcublas' in line})
assert paths and all('/envs/qwen35-vllm/' in p for p in paths), paths
with torch.inference_mode():
    x = torch.randn((2, 1024), device='cuda', dtype=torch.bfloat16)
    w = torch.randn((18432, 1024), device='cuda', dtype=torch.bfloat16)
    y = torch.nn.functional.linear(x, w)
    torch.cuda.synchronize()
    assert torch.isfinite(y).all().item()
report = {'passed': True, 'gpu': os.environ['CUDA_VISIBLE_DEVICES'], 'torch': torch.__version__,
          'cuda': torch.version.cuda, 'cublas_libraries': paths, 'bf16_linear_shape': [2, 1024, 18432]}
Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
