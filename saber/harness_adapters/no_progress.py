"""Bound repeated, evidenced failures without treating reads as failures."""
from __future__ import annotations
import hashlib
import json
import shlex
from dataclasses import dataclass, field


def action_intent(tool, arguments):
    command = arguments.get('command')
    if tool in {'bash', 'saber_bash'} and isinstance(command, str):
        try:
            words = shlex.split(command)
        except ValueError:
            words = [command]
        # Bare flags do not change the failed target. Positional operands,
        # option values, operators and program names stay in the identity.
        normalized = [word for word in words if not word.startswith('-')]
        value = [tool, normalized]
    else:
        value = [tool, arguments]
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass
class NoProgressGuard:
    limit: int = 4
    failures: dict = field(default_factory=dict)

    def observe(self, *, tool, arguments, output, failed, deltas):
        # Unknown effect evidence cannot prove stasis. Conservatively clear the
        # run rather than mistaking a real write or incomplete observation for it.
        if not isinstance(deltas, list) or any(
            not isinstance(d, dict) or d.get('operation') not in {'read', 'inspect', 'list'}
            for d in deltas
        ):
            self.failures.clear()
            return None
        intent = action_intent(tool, arguments)
        if not failed:
            self.failures.pop(intent, None)
            return None
        fingerprint = hashlib.sha256(str(output).encode()).hexdigest()
        previous = self.failures.get(intent)
        count = previous['count'] + 1 if previous and previous['output_sha256'] == fingerprint else 1
        evidence = {'intent_sha256': intent, 'output_sha256': fingerprint, 'count': count,
                    'limit': self.limit, 'terminal': count >= self.limit}
        self.failures[intent] = evidence
        return evidence
