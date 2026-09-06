"""New protocol service configuration; importing never launches work.

Preserves model weights, sampling, GPU pairing and worker counts from v9.
The explicit v10 changes are exact Responses budget counting and dedicated
proxy coverage for the two previously direct-connected backends.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path

from saber_treatment_v9_model_specs import MODEL_SPECS as HISTORICAL_SPECS
from saber_treatment_v9_model_specs import SKILLS_ROOT, _proxy_service, _endpoint

PROTOCOL_VERSION = 'saber-v10-responses-budget-v1'
SOURCE_DEPENDENCIES = [
    SKILLS_ROOT / 'bin/saber_vllm_token_count.py',
    SKILLS_ROOT / 'bin/saber_responses_budget.py',
    SKILLS_ROOT / 'bin/vllm_responses_compat_proxy.py',
    SKILLS_ROOT / 'bin/vllm_responses_compat_proxy_glm47.py',
    SKILLS_ROOT / 'bin/vllm_responses_compat_proxy_gptoss.py',
    SKILLS_ROOT / 'compat/mistral_utf8_v10/sitecustomize.py',
    SKILLS_ROOT / 'compat/mistral_utf8_v10/mistral_utf8_compat.py',
    SKILLS_ROOT / 'compat/mistral_utf8_v10/mistral_tool_strict_compat.py',
    SKILLS_ROOT / 'compat/mistral_utf8_v10/verify_activation.py',
    SKILLS_ROOT / 'compat/mistral_developer_role/sitecustomize.py',
]


def model_specs():
    specs = deepcopy([spec for spec in HISTORICAL_SPECS if spec['key'] in {'mistral', 'minimax', 'deepseek_flash', 'glm', 'gptoss'}])
    for spec in specs:
        spec['protocol_version'] = PROTOCOL_VERSION
        for service in spec['services']:
            argv = service['argv']
            if len(argv) > 1 and argv[1] == 'serve':
                argv.extend(['--middleware', 'saber_vllm_token_count.TokenCountMiddleware'])
                existing = service['env'].get('PYTHONPATH', '')
                service['env']['PYTHONPATH'] = str(SKILLS_ROOT / 'bin') + (':' + existing if existing else '')
        if spec['key'] in {'mistral', 'deepseek_flash'}:
            backend, proxy = (18030, 18031) if spec['key'] == 'mistral' else (18020, 18021)
            spec['services'].append(_proxy_service(
                spec['key'] + '-budget-proxy', 'vllm_responses_compat_proxy.py', proxy, backend))
            spec['endpoints'] = [_endpoint(proxy, range(spec['workers']))]
        if spec['key'] == 'mistral':
            service = spec['services'][0]
            service['env']['PYTHONPATH'] = str(SKILLS_ROOT / 'compat/mistral_utf8_v10') + ':' + service['env']['PYTHONPATH']
            service['env']['SABER_MISTRAL_UTF8_COMPAT_V10'] = '1'
            service['env']['SABER_MISTRAL_TOOL_STRICT_COMPAT_V10'] = '1'
            service['prestart_argv'] = [str(Path(service['argv'][0]).with_name('python')), str(SKILLS_ROOT / 'compat/mistral_utf8_v10/verify_activation.py')]
        for service in spec['services']:
            if any(Path(arg).name.startswith('vllm_responses_compat_proxy') for arg in service['argv']):
                service['env']['SABER_RESPONSES_CONTEXT_GUARD'] = '1'
    return specs


MODEL_SPECS = model_specs()
