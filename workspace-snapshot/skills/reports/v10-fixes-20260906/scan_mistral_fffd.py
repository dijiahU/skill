#!/usr/bin/env python3
"""Read-only U+FFFD inventory for the five SABER v9 raw model result sets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path('/2024233123/skills/results/saber-v9-full-20260905-r1/raw')
MODELS = ('mistral', 'minimax', 'deepseek_flash', 'glm', 'gptoss')
rows = []
summaries = []
for model in MODELS:
    slug = f'codex_{model}_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator'
    files = sorted(p for p in (ROOT / slug).glob('[ABC]/*/*.json') if '_attempts' not in p.name)
    summary = {
        'model': model, 'files': len(files), 'records_with_fffd': 0,
        'assistant_content_records': 0, 'assistant_content_messages': 0,
        'assistant_content_fffd': 0, 'tool_call_records': 0,
        'tool_call_fffd': 0,
    }
    for path in files:
        wire = path.read_bytes()
        data = json.loads(wire)
        assistant_chars = tool_chars = assistant_messages = 0
        for message in data.get('conversation', []):
            if message.get('role') != 'assistant':
                continue
            content = message.get('content')
            if isinstance(content, str):
                found = content.count('\ufffd')
                assistant_chars += found
                assistant_messages += bool(found)
            tool_calls = message.get('tool_calls')
            if isinstance(tool_calls, list):
                tool_chars += json.dumps(tool_calls, ensure_ascii=False).count('\ufffd')
        if assistant_chars or tool_chars:
            rows.append({
                'model': model,
                'task_id': data.get('id') or path.stem,
                'raw_path': str(path),
                'raw_sha256': hashlib.sha256(wire).hexdigest(),
                'assistant_content_fffd': assistant_chars,
                'assistant_content_messages': assistant_messages,
                'tool_call_fffd': tool_chars,
            })
        summary['records_with_fffd'] += bool(assistant_chars or tool_chars)
        summary['assistant_content_records'] += bool(assistant_chars)
        summary['assistant_content_messages'] += assistant_messages
        summary['assistant_content_fffd'] += assistant_chars
        summary['tool_call_records'] += bool(tool_chars)
        summary['tool_call_fffd'] += tool_chars
    summaries.append(summary)

output = {
    'schema_version': 'saber-mistral-fffd-inventory-v1',
    'scope': {'raw_root': str(ROOT), 'trajectory_commands_executed': False},
    'summaries': summaries,
    'affected_records': rows,
}
out = Path('/2024233123/skills/reports/v10-fixes-20260906/mistral_fffd_inventory.json')
out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'output': str(out), 'summaries': summaries}, ensure_ascii=False, indent=2))
