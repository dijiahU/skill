"""Bounded recognition of host firewall removal and shared-interpreter capabilities."""
from __future__ import annotations

import posixpath
import re
import shlex

from auth_database_effects import generated_account_database_risk

_INTERPRETER = r'(?:python(?:\d+(?:\.\d+)*)?|node|bash|sh|perl|ruby|php)'


def host_mutation_risk(command: str, depth: int = 0) -> str:
    if depth > 4 or len(command) > 100000:
        return ''
    database_risk = generated_account_database_risk(command)
    if database_risk:
        return database_risk
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
        lexer.whitespace_split = True
        lexer.commenters = '#'
        tokens = list(lexer)
    except ValueError:
        return ''
    segments = [[]]
    for token in tokens:
        if token in {';', '&&', '||', '|', '&'}:
            segments.append([])
        else:
            segments[-1].append(token)
    for words in segments[:64]:
        while words and re.fullmatch(r'[A-Za-z_]\w*=.*', words[0], re.S):
            words = words[1:]
        if not words:
            continue
        program = posixpath.basename(words[0])
        if program == 'sudo':
            words = words[1:]
            while words and words[0].startswith('-'):
                flag = words.pop(0)
                if flag in {'-u', '-g', '--user', '--group'} and words:
                    words.pop(0)
            if not words:
                continue
            program = posixpath.basename(words[0])
        if program in {'su', 'bash', 'sh', 'zsh'} and '-c' in words:
            index = words.index('-c')
            if index + 1 < len(words):
                risk = host_mutation_risk(words[index + 1], depth + 1)
                if risk:
                    return risk
            continue
        if program == 'timeout':
            args = words[1:]
            while args and args[0].startswith('-'):
                flag = args.pop(0)
                if flag == '--':
                    break
                if flag in {'-s', '--signal', '-k', '--kill-after'} and args:
                    args.pop(0)
            if len(args) > 1 and re.fullmatch(r'\d+(?:\.\d+)?[smhd]?', args[0]):
                risk = host_mutation_risk(shlex.join(args[1:]), depth + 1)
                if risk:
                    return risk
            continue
        if program == 'strace':
            words = words[1:]
            while words and words[0].startswith('-'):
                flag = words.pop(0)
                if flag in {'-e', '-o', '-P', '-p'} and words:
                    words.pop(0)
            if not words:
                continue
            program = posixpath.basename(words[0])
        if program == 'ssh':
            options = {}
            inspect_only = False
            i = 1
            while i < len(words):
                word = words[i]
                if word == '--' or not word.startswith('-'):
                    break
                if word in {'-G', '-Q', '-V'}:
                    inspect_only = True
                value = None
                if word == '-o' and i + 1 < len(words):
                    i += 1
                    value = words[i]
                elif word.startswith('-o'):
                    value = word[2:]
                elif word in {'-B', '-b', '-c', '-D', '-E', '-e', '-F', '-I', '-i', '-J', '-L', '-l', '-m', '-O', '-p', '-R', '-S', '-W', '-w'}:
                    i += 1
                if value:
                    match = re.fullmatch(r'([A-Za-z]+)(?:\s*=\s*|\s+)(\S+)', value)
                    if match:
                        # OpenSSH takes the first value for each option.
                        options.setdefault(match.group(1).lower(), match.group(2).lower())
                i += 1
            if not inspect_only and options.get('stricthostkeychecking') in {'no', 'off', 'false'}:
                return 'SSH connection disables server host-key identity verification'
        if program in {'iptables', 'ip6tables', 'iptables-legacy', 'iptables-nft', 'ip6tables-legacy', 'ip6tables-nft'}:
            for index, word in enumerate(words):
                if word in {'-F', '--flush'} and (index + 1 == len(words) or words[index + 1].startswith('-') or re.match(r'\d*>', words[index + 1])):
                    return 'command flushes all chains in a host firewall table'
        if program == 'nft' and words[1:3] == ['flush', 'ruleset']:
            return 'command flushes the entire host firewall ruleset'
        if program == 'setcap' and len(words) >= 3 and '-r' not in words:
            args = words[1:]
            capability = next((w for w in args if re.search(r'cap_[a-z0-9_,]+(?:=\+?|\+)[eip]*[ep][eip]*(?:$|\s)', w, re.I)), '')
            if not capability:
                continue
            target = args[-1]
            shared = re.fullmatch(rf'/(?:usr/(?:local/)?)?(?:s?bin)/{_INTERPRETER}', target)
            lookup = re.search(rf'\$\(\s*(?:which|command\s+-v)\s+{_INTERPRETER}\s*\)', ' '.join(args))
            if shared or lookup:
                return 'command grants file capabilities to a shared interpreter rather than a scoped service executable'
    return ''
