"""Audited multi-service Docker support for the pinned Terminal-Bench task set."""
import asyncio
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import uuid
import time
from dockerfile_transport import render
from network_pool import reserve
from ensembl_transport import adapt as adapt_ensembl
from dependency_transport import adapt as adapt_dependencies

import yaml
from aistation import AIStationDocker, host_path
from harbor.environments.base import ExecResult
from harbor.environments.docker.docker import DockerEnvironment

CACHE = Path('/srv/benchmark/skills/cache/terminal-bench-build')


def direct_download_env(env=None):
    env = dict(os.environ if env is None else env)
    if os.environ.get('TERMINAL_BENCH_DIRECT_DOWNLOAD') == '1':
        for key in ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
            env.pop(key, None)
        env.update(no_proxy='*', NO_PROXY='*')
    return env


def run(argv, **kwargs):
    kwargs['env'] = direct_download_env(kwargs.get('env'))
    return subprocess.run(argv, check=True, **kwargs)


def cache_image(reference):
    if reference == 'scratch':
        return reference
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(reference.encode()).hexdigest()
    tag = 'rick-saber-tb-base:' + key[:24]
    with (CACHE/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode == 0:
            return tag
        attempt = key + '-' + uuid.uuid4().hex
        source = CACHE/(attempt+'.upstream.tar')
        if not source.exists():
            proxy = os.environ.get('TERMINAL_BENCH_DOWNLOAD_PROXY')
            env = dict(os.environ)
            if proxy:
                env.update({key:proxy for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY')})
            download_reference = reference
            mirror = os.environ.get('TERMINAL_BENCH_IMAGE_MIRROR', '').strip('/')
            if mirror and not reference.startswith(('ghcr.io/', 'gcr.io/', 'quay.io/')):
                download_reference = mirror + '/' + reference.removeprefix('docker.io/')
            run(['/srv/benchmark/skills/bin/crane','pull','--platform','linux/amd64',download_reference,str(source)],timeout=1800,env=env)
            (CACHE/(attempt+'.download.json')).write_text(json.dumps({
                'upstream_reference':reference, 'download_reference':download_reference,
                'http_proxy_used':False, 'project_tag':tag}, indent=2))
        target = CACHE/(attempt+'.project.tar')
        if not target.exists():
            with tarfile.open(source) as incoming, tarfile.open(target,'w') as outgoing:
                for item in incoming:
                    stream=incoming.extractfile(item) if item.isfile() else None
                    if item.name=='manifest.json':
                        data=json.load(stream)
                        for image in data:
                            image['RepoTags']=[tag]
                        content=json.dumps(data).encode();item.size=len(content);stream=io.BytesIO(content)
                    outgoing.addfile(item,stream)
        run(['docker','load','-i',str(target)],timeout=300)
        return tag


def audit_compose(path):
    if not path.exists():
        return {'main':{}}
    data=yaml.safe_load(path.read_text())
    if set(data)-{'services','name','version'}:
        raise ValueError('Task declares global Docker resources: '+str(path))
    services=data['services']
    for name, spec in services.items():
        if any(spec.get(key) for key in ('privileged','volumes','ports','devices','container_name','pid','ipc','volumes_from','extends')):
            raise ValueError('Host-affecting service definition: '+name)
        if set(spec.get('cap_add', [])) - {'SYS_PTRACE'}:
            raise ValueError('Unsupported additional capabilities: '+name)
        mode=spec.get('network_mode','')
        if mode and (not mode.startswith('service:') or mode[8:] not in services):
            raise ValueError('Unsupported task network mode: '+mode)
        build=spec.get('build')
        if build:
            build={'context':build} if isinstance(build,str) else build
            if set(build)-{'context','dockerfile','args','target','no_cache'}:
                raise ValueError('Unsupported build options: '+name)
            context=(path.parent/build.get('context','.')).resolve()
            context.relative_to(path.parent.resolve())
            (context/build.get('dockerfile','Dockerfile')).resolve().relative_to(path.parent.resolve())
    return services


class BatchDocker(AIStationDocker):
    def __init__(self,*args,**kwargs):
        path=Path(kwargs['environment_dir'])/'docker-compose.yaml'
        self._batch_services=audit_compose(path)
        kwargs['allow_audited_compose']=True
        super().__init__(*args,**kwargs)
        self._env_vars.main_image_name += '-repair2'
        dockerfile = Path(kwargs['environment_dir']) / 'Dockerfile'
        if dockerfile.exists() and 'perl INSTALL.pl --AUTO a --NO_HTSLIB --NO_TEST --NO_UPDATE' in dockerfile.read_text():
            self._env_vars.main_image_name += '-git-version'
        if dockerfile.exists() and re.match(r'^#\s*syntax=', dockerfile.read_text()):
            self._env_vars.main_image_name += '-builtin'
        if dockerfile.exists():
            _, dependency_repairs = adapt_dependencies(dockerfile.read_text(), repair_uv=Path(kwargs['environment_dir']).parent.name in {'gsea-proteomics', 'roy-polymorph-cn'})
            if dependency_repairs:
                self._env_vars.main_image_name += '-' + '-'.join(dependency_repairs)
        runtime=json.loads(self._runtime_path.read_text())
        for name,spec in self._batch_services.items():
            entry=runtime['services'].setdefault(name,{})
            entry.update(runtime='runc',pull_policy='never',labels={
                'skilldistill.benchmark':'terminal-bench','skilldistill.session':self.session_id})
            proxy = os.environ.get('TERMINAL_BENCH_DOWNLOAD_PROXY')
            if proxy:
                bypass = ','.join(['localhost','127.0.0.1',*self._batch_services])
                entry['environment'] = {key:proxy for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY')}
                entry['environment'].update(no_proxy=bypass, NO_PROXY=bypass)
            if os.environ.get('TERMINAL_BENCH_DIRECT_DOWNLOAD') == '1':
                entry.setdefault('environment', {}).update({key:'' for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')})
                entry['environment'].update(no_proxy='*', NO_PROXY='*',
                    PIP_INDEX_URL=os.environ['PIP_INDEX_URL'], PIP_EXTRA_INDEX_URL='',
                    UV_DEFAULT_INDEX=os.environ['PIP_INDEX_URL'], UV_INDEX_URL=os.environ['PIP_INDEX_URL'],
                    PIP_DEFAULT_TIMEOUT='120', PIP_RETRIES='5')
            if not self.task_env_config.docker_image or name!='main':
                entry['image']=self._env_vars.main_image_name if name=='main' else self._env_vars.main_image_name+'-'+name
        if not self.task_env_config.docker_image:
            runtime['services']['main'].update(image=self._env_vars.main_image_name,pull_policy='never')
        runtime['services']['main'].setdefault('volumes', []).append({
            'type':'bind',
            'source':host_path('/srv/benchmark/skills/envs/uv-python/cpython-3.12.14-linux-x86_64-gnu'),
            'target':'/opt/terminal-bench-observer-python', 'read_only':True})
        self._runtime_path.write_text(json.dumps(runtime,indent=2))

    async def start(self, force_build=False):
        subnet = await asyncio.to_thread(reserve, self.session_id)
        runtime = json.loads(self._runtime_path.read_text())
        runtime['networks'] = {'default': {'ipam': {'config': [{'subnet': subnet}]},
            'labels': {'skilldistill.benchmark':'terminal-bench','skilldistill.session':self.session_id}}}
        self._runtime_path.write_text(json.dumps(runtime, indent=2))
        await super().start(force_build=force_build)

    def _build(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        key=hashlib.sha256(self._env_vars.main_image_name.encode()).hexdigest()
        with (CACHE/(key+'.build.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self._build_locked()

    def _build_locked(self):
        runtime=json.loads(self._runtime_path.read_text())
        services={'main':{},**self._batch_services}
        for name,spec in services.items():
            tag=runtime['services'][name]['image']
            if spec.get('image') and not spec.get('build'):
                runtime['services'][name]['image']=cache_image(spec['image'])
                continue
            if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode==0:
                continue
            build=spec.get('build',{})
            build={'context':build} if isinstance(build,str) else build
            context=(self.environment_dir/build.get('context','.')).resolve()
            dockerfile=context/build.get('dockerfile','Dockerfile')
            rendered=self._retained_dir/(name+'.Dockerfile')
            source, adapted = adapt_ensembl(dockerfile.read_text())
            source, dependency_repairs = adapt_dependencies(source, repair_uv=self.environment_dir.parent.name in {'gsea-proteomics', 'roy-polymorph-cn'})
            if os.environ.get('TERMINAL_BENCH_DIRECT_DOWNLOAD') == '1':
                # Keep earlier cached CPU-PyTorch layers; only the subsequent package
                # installation needs new mirror settings. Explicit upstream index
                # commands retain their pinned CPU wheel selection.
                source = source.replace('RUN pip install --no-cache-dir ' + chr(92) + chr(10),
                    'ARG PIP_INDEX_URL\nARG PIP_DEFAULT_TIMEOUT=120\nARG PIP_RETRIES=5\n'
                    + 'RUN pip install --no-cache-dir ' + chr(92) + chr(10))
            rendered.write_text(render(source, cache_image))
            argv=['docker','buildx','build','--load','--network=host','--progress=plain',
                  '-f',str(rendered),'-t',tag]
            proxy=os.environ.get('TERMINAL_BENCH_DOWNLOAD_PROXY')
            if proxy:
                for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY'):
                    argv+=['--build-arg',key+'='+proxy]
            if os.environ.get('TERMINAL_BENCH_DIRECT_DOWNLOAD') == '1':
                for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):
                    argv += ['--build-arg', key+'=']
                argv += ['--build-arg', 'no_proxy=*', '--build-arg', 'NO_PROXY=*',
                    '--build-arg', 'PIP_INDEX_URL='+os.environ['PIP_INDEX_URL']]
            for key,value in build.get('args',{}).items():
                argv+=['--build-arg',f'{key}={value}']
            if build.get('target'): argv+=['--target',build['target']]
            argv.append(str(context))
            for attempt in range(3):
                logfile=self._retained_dir/(name+'-build'+('' if attempt==0 else '-retry'+str(attempt))+'.log')
                try:
                    with logfile.open('x') as log:
                        run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                    break
                except subprocess.CalledProcessError:
                    message=logfile.read_text(errors='replace').lower()
                    deterministic = any(marker in message for marker in ('uninstall-distutils-installed-package', 'uv: not found', 'resolutionimpossible'))
                    transient=not deterministic and any(marker in message for marker in (
                        '502', '503', '504', 'timed out', 'timeout', 'connection reset',
                        'could not resolve', 'partial file', 'not closed cleanly',
                        'ssl_error_syscall', 'operation too slow', 'failed to download'))
                    if attempt==2 or not transient:
                        raise
                    if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode==0:
                        break
                    time.sleep(2**attempt)
        self._runtime_path.write_text(json.dumps(runtime,indent=2))

    async def _run_docker_compose_command(self,command,**kwargs):
        if command[0]=='build':
            await asyncio.to_thread(self._build)
            return ExecResult(stdout='Project images prepared',stderr='',return_code=0)
        if command[0]=='up':
            command=[*command,'--no-build','--pull','never']
        return await super()._run_docker_compose_command(command,**kwargs)
