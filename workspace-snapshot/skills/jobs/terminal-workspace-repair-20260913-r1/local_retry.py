import importlib.util
import os
from pathlib import Path
from terminal_common import JOB, run_terminal

spec = importlib.util.spec_from_file_location('prior_protocol_probe',
    Path('/srv/benchmark/skills/jobs/gptoss-oas-terminal-20260913-r1/arm_runner.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
probe.JOB = JOB
probe.protocol_probe('terminal')
run_terminal('gptoss', os.environ['GPTOSS_BASE_URL'], 'EMPTY')
