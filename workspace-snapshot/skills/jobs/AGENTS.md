# GPU Job Guidelines

Apply /2024233123/AGENTS.md safety boundaries.

For new GPU work while the idle controller is enabled, launch the complete
model-server-and-consumer lifecycle with
/2024233123/skills/bin/gpu-idle run --gpus <physical GPU IDs> -- <command>.
This reserves those cards and waits for the idle Qwen replica to release memory
before the foreground command starts. Match --gpus to the script's actual
CUDA_VISIBLE_DEVICES; never request one card for a script that uses both.

Use gpu-idle status to check the controller and gpu-idle stop for normal shutdown.
Do not launch the older single/dual forever burn-in scripts concurrently.
Never stop an unrelated model server to free a GPU. Running but idle model
servers still own their cards. Jobs in other Pods are not automatically admitted
through this local controller.

See gpu_idle_README.md for commands and limitations. Run tests/test_gpu_idle.py
after changing admission, preemption, process identity, or container ownership.
