"""Official TB 2.1 images under isolated project tags; no host cleanup."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from verifier_integrity import assess_verifier
from batch_docker import BatchDocker, cache_image
from aistation import host_path


def project_image(reference):
    return 'rick-saber-tb-base:' + hashlib.sha256(reference.encode()).hexdigest()[:24]


class VerifierIntegrityError(RuntimeError):
    pass


class TB21Docker(BatchDocker):
    def __init__(self, *args, **kwargs):
        config = kwargs['task_env_config'].model_copy(deep=True)
        self.upstream_image = config.docker_image
        if not self.upstream_image:
            raise ValueError('Terminal-Bench 2.1 requires its declared official image')
        config.docker_image = project_image(self.upstream_image)
        kwargs['task_env_config'] = config
        super().__init__(*args, **kwargs)
        self._env_vars.main_image_name = config.docker_image
        self._env_vars.prebuilt_image_name = config.docker_image
        runtime = json.loads(self._runtime_path.read_text())
        runtime['services']['main'].update(image=config.docker_image, pull_policy='never')
        runtime['services']['main'].setdefault('volumes', []).append({
            'type':'bind',
            'source':host_path('/srv/benchmark/skills/jobs/terminal-bench-2.1-full-20260911-r1/verifier-bootstrap'),
            'target':'/opt/tb21-verifier-bootstrap', 'read_only':True})
        # Avoid Kubernetes search-domain expansion for public package hosts.
        runtime['services']['main']['dns_opt'] = ['ndots:1', 'timeout:2', 'attempts:2']
        runtime['services']['main'].setdefault('environment', {}).update(
            RES_OPTIONS='ndots:1 timeout:2 attempts:2',
            UV_FIND_LINKS='/opt/tb21-verifier-bootstrap/wheels')
        proxy = os.environ.get('TERMINAL_BENCH_DOWNLOAD_PROXY')
        if not proxy:
            raise ValueError('Verified package proxy must be configured for TB 2.1')
        env = runtime['services']['main']['environment']
        env.update({key: proxy for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy')})
        env.update(ALL_PROXY='', all_proxy='', NO_PROXY='localhost,127.0.0.1', no_proxy='localhost,127.0.0.1',
                   PIP_INDEX_URL='https://pypi.org/simple', PIP_EXTRA_INDEX_URL='',
                   UV_DEFAULT_INDEX='https://pypi.org/simple', UV_INDEX_URL='https://pypi.org/simple')
        self._runtime_path.write_text(json.dumps(runtime, indent=2))
        self._write('upstream-image.json', {'upstream':self.upstream_image, 'project_image':config.docker_image})

    def _build(self):
        actual = cache_image(self.upstream_image)
        if actual != self.task_env_config.docker_image:
            raise RuntimeError('Project image identity mismatch')

    async def start(self, force_build=False):
        if force_build:
            raise ValueError('Forced image replacement is disabled')
        await asyncio.to_thread(self._build)
        await super().start(force_build=False)

    async def exec(self, command, **kwargs):
        # The pinned Harbor verifier command has both paths; agent commands do not.
        verifying = '/tests/test.sh' in command and '/logs/verifier/test-stdout.txt' in command
        directory = self.trial_paths.verifier_dir
        if verifying and any((directory / name).exists() for name in ('ctrf.json', 'reward.txt', 'reward.json')):
            raise VerifierIntegrityError('Refusing stale verifier artifacts; use a fresh regrade directory')
        result = await super().exec(command=command, **kwargs)
        if verifying:
            reward_path = directory / 'reward.txt'
            try:
                reward = float(reward_path.read_text())
            except (OSError, ValueError):
                reward = None
            integrity = assess_verifier(directory, reward)
            (directory / 'execution-integrity.json').write_text(json.dumps(integrity, indent=2) + '\n')
            if not integrity['valid']:
                raise VerifierIntegrityError(integrity['reason'])
        return result
