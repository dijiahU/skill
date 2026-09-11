"""Bounded review of proposed effects, independent of earlier tool denials.

Only inspect text and the host's workspace view. Never execute generated
commands, trust answer-supplied approval, or return source/credential values.
"""

import hashlib
import json
import os
import re
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lib_common import _state_dir

from matcher_bash import (
    _automation_controller_risk, _automation_controllers, _workspace_snapshot,
    _automation_semantic_risk, _automation_token_segments, _strip_command_prefix,
    _is_sensitive_credential_path,
)


_RUN = re.compile(r"运行|执行|调用|\b(?:run|execute|invoke|apply)\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"(?:不要|请勿|不能|不应(?:该)?|不会|不再|不建议|不使用|不用|不|拒绝|无需|不需要|未|没有)"
    r"\s*(?:直接|继续|手动|自行|再)?\s*$|"
    r"\b(?:do not|don't|never|cannot|can't|will not|won't|must not|should not|"
    r"no need to|need not|refuse to|refused to|without using|without)\s+(?:directly\s+|manually\s+)?$",
    re.IGNORECASE,
)
_REJECTED = re.compile(
    r"不可选|不可执行|已排除|拒绝了|已拒绝|不(?:予|被)允许|禁止(?:执行|选择)|"
    r"\b(?:not (?:an? )?option|not selectable|rejected|forbidden|do not choose)\b",
    re.IGNORECASE,
)
_MENU = re.compile(
    r"方案|选项|建议|后续步骤|解决方法|\b(?:options?|choices?|alternatives?|next steps|recommendations?)\b",
    re.IGNORECASE,
)
_OPTION_START = re.compile(
    r"(?m)^\s*(?:[-+*]\s+|\d{1,2}[.)、]\s*|"
    r"(?:方案|选项|option|choice|plan)\s*[0-9A-Z一二三四五六七八九十甲乙丙丁]+[^\n:：]{0,15}[:：])",
    re.IGNORECASE,
)
_DIRECTIVE = re.compile(
    r"(?:你可以|建议|请|直接|继续|手动|自行|然后|之后)[^。\n;；]{0,55}(?:运行|执行|调用)|"
    r"\b(?:you can|you should|please|I recommend)\b[^\n.;]{0,65}\b(?:run|execute|invoke|apply)\b|"
    r"(?:^\s*|\bthen\s+)(?:run|execute|invoke|apply)\b",
    re.IGNORECASE,
)
_CLAUSE = re.compile(
    r"[。;；]|(?<=[.!?])\s+|\b(?:but|however|nevertheless)\b|但是|不过|然而|但",
    re.IGNORECASE,
)
_READ_TOOL = re.compile(r"^\s*[`'\"]?(?:cat|head|tail|less|more|grep|rg|stat|ls)\b")
_READ_PURPOSE = re.compile(
    r"(?:查看|检查|读取|审计|解释|分析)[^。\n;；]{0,35}$|"
    r"\b(?:inspect|read|review|explain|audit|analyze)\b[^\n.;]{0,35}$",
    re.IGNORECASE,
)
_HARM = (
    ("database-wide destruction", re.compile(
        r"(?:清空|删除|删掉|销毁|抹掉|清除|擦除)\s*(?:(?:所有|全部)(?:的)?(?:数据)?表|"
        r"整个数据库|(?:所有|全部)(?:的)?(?:数据|记录)|生产数据库)|"
        r"\b(?:drops?|truncates?|deletes?|wipes?|erases?|destroys?|purges?|empty|empties)\s+"
        r"(?:(?:all|every)\s+(?:the\s+)?(?:database\s+)?tables?|"
        r"(?:the\s+)?(?:entire|production)\s+database|all\s+(?:the\s+)?(?:data|records))\b",
        re.IGNORECASE,
    )),
    ("raw credential disclosure", re.compile(
        r"(?:打印|输出|上传|发送|导出|公开|泄露)[^。\n;；]{0,25}"
        r"(?:原始凭证|凭证值|私钥|访问令牌|明文密码|敏感环境变量)|"
        r"\b(?:print|dump|upload|send|share|expose)\b[^\n.;]{0,40}"
        r"\b(?:raw credentials?|private keys?|access tokens?|plaintext passwords?)\b",
        re.IGNORECASE,
    )),
    ("safety-gate bypass", re.compile(
        r"(?:绕过|禁用|关闭|跳过)[^。\n;；]{0,25}(?:安全(?:检查|防护|策略)|Safety(?: Router| Orchestrator)?|审批)|"
        r"\b(?:bypass|disable|skip)\b[^\n.;]{0,35}\b(?:safety checks?|safety router|approval gates?)\b",
        re.IGNORECASE,
    )),
)
_INLINE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")


_COMMAND_TEXT = re.compile(
    r"(?<![\w./])(?:bash|sh|zsh|python(?:\d+(?:\.\d+)*)?|node|make|gmake|npm|chmod|sudo)\s+"
    r"[^\n`，。;；()（）,]+"
)
_EXECUTION_LEAD = re.compile(
    r"(?:运行|执行|调用|\b(?:run|execute|invoke|apply))\s*"
    r"(?:(?:locally|manually)\s*)?[:：]?\s*$", re.IGNORECASE,
)
_REPAIR = re.compile(r"修改|修复|重写|\b(?:modify|edit|repair|rewrite)\b", re.IGNORECASE)
_LIMITED_SCOPE = re.compile(
    r"(?:只|仅)(?:探测|扫描|访问)(?:已)?(?:批准|授权)(?:的)?(?:子网|范围|网络|目标)|"
    r"\b(?:only\s+(?:probe|scan|access)|(?:probe|scan|access)\s+only)\s+"
    r"(?:the\s+)?(?:approved|authorized)\s+(?:scope|subnets?|networks?|ranges?|targets?)\b",
    re.IGNORECASE,
)
_SEQUENCE = re.compile(r"然后|之后|再|\bthen\b", re.IGNORECASE)
_AUDIT_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:审计(?:结论|记录|结果)|风险分析|原因分析|"
    r"(?:audit|review)\s+(?:findings?|results|notes)|rejected alternatives)\s*[:：]",
    re.IGNORECASE,
)


def _units(text: str) -> Iterator[tuple[str, bool]]:
    """Retain choice headers across blank lines, but isolate audit sections."""
    buffer: list[str] = []
    menu_context = False
    listed = False
    for line in text.splitlines():
        option = _OPTION_START.match(line)
        heading = _AUDIT_HEADING.match(line)
        menu_header = bool(_MENU.search(line) and not _RUN.search(line) and line.rstrip().endswith((":", "：")))
        if option or heading or menu_header:
            if buffer:
                yield "\n".join(buffer), listed
            buffer = []
            if heading:
                menu_context = False
            elif menu_header:
                menu_context = True
            explicit_choice = bool(option and re.search(r"方案|选项|option|choice|plan", option.group(), re.IGNORECASE))
            listed = bool(option and (menu_context or explicit_choice))
        buffer.append(line)
    if buffer:
        yield "\n".join(buffer), listed


def _scoped_repair_precedes(prefix: str, path: Path, cwd: str) -> bool:
    """A same-file, explicit narrow-scope edit precedes this proposed invocation.

    This is a conditional repair plan, not a claim that the present file is safe.
    Actual execution still goes through PreTool review of the updated snapshot.
    """
    repairs = list(_REPAIR.finditer(prefix))
    if not repairs:
        return False
    plan = prefix[repairs[-1].end():]
    limited = _LIMITED_SCOPE.search(plan)
    if not limited:
        return False
    references = re.finditer(
        rf"(?<![A-Za-z0-9_./-])(?P<path>(?:[A-Za-z0-9_./-]+/)?{re.escape(path.name)})(?![A-Za-z0-9_.-])",
        plan[:limited.start()],
    )
    same_file = False
    for reference in references:
        named = Path(reference.group("path"))
        resolved = (named if named.is_absolute() else Path(cwd) / named).resolve()
        same_file |= resolved == path.resolve()
    sequence = _SEQUENCE.search(plan[limited.end():])
    return bool(same_file and sequence and _RUN.search(plan[limited.end() + sequence.end():]))


_FENCED_CODE = re.compile(r"^[ \t]*```[^`\n]*\n(.*?)^[ \t]*```[ \t]*(?=\n|$)", re.IGNORECASE | re.DOTALL | re.MULTILINE)
_REFUSAL_CONTEXT = re.compile(
    r"(?:不要|请勿|拒绝|不能|不会|不应|禁止)[^。\n]{0,80}$|"
    r"\b(?:do not|don't|never|refuse(?:d)?|cannot|can't|will not|won't|must not)\b[^.\n]{0,100}$",
    re.IGNORECASE,
)


def _proposal_context_key(event: dict[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest() if session or turn else "default"


def _proposal_auth_path(event: dict[str, Any]) -> Path:
    return _state_dir() / f"output-proposal-auth-{_proposal_context_key(event)}.json"


def _explicit_action_request(prompt: str) -> bool:
    return bool(re.search(
        r"(?is)(?:帮我|请|需要你|给我)[^。\n]{0,24}(?:设置|写|创建|添加|配置|安装)|"
        r"^\s*(?:please\s+)?(?:write|create|set\s+up|configure|add|install)\b|"
        r"\b(?:can|could|would)\s+you\s+(?:please\s+)?(?:write|create|set\s+up|configure|add|install)\b|"
        r"\bI\s+(?:want|need)\s+you\s+to\s+(?:write|create|set\s+up|configure|add|install)\b",
        prompt,
    ))


def _negates_prompt_action(prompt: str, subject: str) -> bool:
    if subject == "cron":
        target = r"(?:crontab|cron|开机|重启|reboot|boot)"
    else:
        target = r"(?:pre-commit|precommit|代码|变更|diff|code|changes?|send|upload)"
    return bool(re.search(
        rf"(?is)(?:不要|请勿|不能|不应|无需|别)[^。\n]{{0,45}}{target}|"
        rf"\b(?:do\s+not|don't|never|must\s+not|should\s+not|without)\b[^.\n]{{0,60}}{target}",
        prompt,
    ))


def _requested_workspace_paths(prompt: str, cwd: str) -> list[str]:
    if not cwd:
        return []
    found: list[str] = []
    for raw in re.findall(
        r"(?<![\w.-])(?:/|\.{1,2}/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:py|sh|js|mjs|cjs)(?![\w.-])",
        prompt,
    ):
        path = Path(raw)
        resolved = path.resolve() if path.is_absolute() else (Path(cwd) / path).resolve()
        found.append(str(resolved))
    return sorted(set(found))[:16]


def record_output_proposal_authorization(event: dict[str, Any]) -> None:
    """Persist narrow final-output permissions derived only from a user prompt."""
    prompt = str(event.get("prompt") or event.get("user_prompt") or "")
    cwd = str(event.get("cwd") or "")
    classes: list[str] = []
    explicit_urls: list[str] = []
    requested_paths: list[str] = []
    if (_explicit_action_request(prompt)
            and not _negates_prompt_action(prompt, "cron")
            and cwd
            and re.search(r"(?is)(?<![A-Za-z0-9_])crontab(?![A-Za-z0-9_])", prompt)
            and re.search(r"重启|开机|\b(?:reboot|boot)\b", prompt)
            and re.search(r"自动运行|自动启动|自己跑|\b(?:automatically\s+)?(?:run|start)\b", prompt)
            and not re.search(r"(?i)\b(?:sudo|root)\b|/etc/(?:crontab|cron)|systemd|rc\.local", prompt)):
        classes.append("user_reboot_crontab")
        requested_paths = _requested_workspace_paths(prompt, cwd)
    if (_explicit_action_request(prompt)
            and not _negates_prompt_action(prompt, "review")
            and re.search(r"(?is)\b(?:pre-commit|precommit)\b", prompt)
            and re.search(r"代码|变更|diff|changes?|source", prompt, re.IGNORECASE)
            and re.search(r"发送|上传|审查|send|upload|review", prompt, re.IGNORECASE)
            and re.search(r"我的服务器|自有服务器|my server|our server", prompt, re.IGNORECASE)):
        classes.append("staged_diff_review")
        explicit_urls = sorted(set(
            value.rstrip(".,;:!?，。；：！？)")
            for value in re.findall(r"https?://[^\s'\"`<>]+", prompt, re.IGNORECASE)
        ))[:8]
    payload = {
        "schema_version": 1,
        "allowed_classes": sorted(set(classes)),
        "explicit_urls": explicit_urls,
        "workspace_root": str(Path(cwd).resolve()) if cwd else "",
        "requested_paths": requested_paths,
    }
    path = _proposal_auth_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _proposal_authorization(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    try:
        payload = json.loads(_proposal_auth_path(event).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _authorized_user_reboot_fence(code: str, authorization: dict[str, Any], cwd: str) -> bool:
    if "user_reboot_crontab" not in authorization.get("allowed_classes", []):
        return False
    if re.search(
        r"(?i)\b(?:sudo|doas)\b|\bcrontab\s+-u\b|/etc/(?:crontab|cron)|"
        r"\bsystemctl\b|rc\.local",
        code,
    ):
        return False
    authorized_root = str(authorization.get("workspace_root") or "")
    if not cwd or not authorized_root or Path(cwd).resolve() != Path(authorized_root).resolve():
        return False
    stripped = code.strip()
    # The editor invocation and the cron entry commonly appear in separate
    # fences. Only the current user's plain editor invocation is exempted.
    if re.fullmatch(r"crontab\s+-e", stripped):
        return True
    entries = [line.strip() for line in code.splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    if not entries or any(not line.startswith("@reboot ") for line in entries):
        return False
    forbidden = re.compile(
        r"(?i)\b(?:curl|wget|nc|ncat|socat|ssh|scp|rsync|bash|sh)\b|"
        r"(?:\.env|\.ssh|credentials?|secrets?|tokens?|/etc/)|"
        r"\brm\b|\bchmod\b|\bchown\b|\$\(|`",
    )
    if forbidden.search(code):
        return False
    root = Path(authorized_root).resolve()
    requested_paths = {str(Path(value).resolve()) for value in authorization.get("requested_paths", [])}
    for line in entries:
        command = line.removeprefix("@reboot ").split(">", 1)[0].strip()
        try:
            words = shlex.split(command)
        except ValueError:
            return False
        if not words:
            return False
        target = words[1] if Path(words[0]).name.startswith("python") and len(words) > 1 else words[0]
        if not target.startswith("/"):
            return False
        path = Path(target).resolve()
        if path != root and root not in path.parents:
            return False
        if requested_paths and str(path) not in requested_paths:
            return False
        if not requested_paths and path.name not in {"app.py", "main.py", "run.py", "server.py"}:
            return False
    return True


def _literal_shell_assignments(code: str) -> dict[str, str]:
    return {
        name: value
        for name, _, value in re.findall(
            r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*([\"'])([^\n\"']*)\2(?:\s*#.*)?\s*$", code
        )
        if "$" not in value and "`" not in value
    }


def _authorized_staged_review_fence(code: str, authorization: dict[str, Any]) -> bool:
    if "staged_diff_review" not in authorization.get("allowed_classes", []):
        return False
    # Only a staged Git diff may feed the review request. Any added filesystem
    # or credential source is outside this narrow permission.
    staged_assignments = re.findall(
        r"(?m)^\s*STAGED_DIFF\s*=\s*\$\(([^\n()]*)\)\s*(?:#.*)?$",
        code,
    )
    if len(staged_assignments) != 1 or not re.fullmatch(
        r"\s*git\s+diff\s+(?=[^\n]*--cached)(?=[^\n]*--binary)"
        r"(?:--cached|--binary|--no-ext-diff|--no-color|\s)+",
        staged_assignments[0],
        re.IGNORECASE,
    ):
        return False
    if re.search(
        r"(?i)(?:\.env|\.ssh|private[_ -]?key|credentials?|secrets?|tokens?|"
        r"authorization|api[_ -]?key|cookies?|/etc/(?:shadow|sudoers)|"
        r"\b(?:cat|head|tail|jq|tar|zip|source|read)\b|"
        r"(?:^|[;&|$(])\s*(?:/usr/bin/)?(?:env|printenv)\b)",
        code,
    ):
        return False
    assignments = _literal_shell_assignments(code)
    curl = re.search(r"(?is)\bcurl\b.{0,1200}", code)
    if not curl:
        return False
    curl_text = curl.group()
    if not re.search(r"(?i)(?:-X\s*POST|--data(?:-binary)?|-d\s)", curl_text):
        return False
    data_arguments = re.findall(
        r"(?i)(?:--data(?:-binary)?|-d)\s+(\"[^\"\n]*\"|'[^'\n]*'|\S+)",
        curl_text,
    )
    if not data_arguments or any(
        not re.fullmatch(r"[\"']?\$\{?STAGED_DIFF\}?[\"']?", argument)
        for argument in data_arguments
    ):
        return False
    urls = re.findall(r"https?://[^\s'\"`<>]+", curl_text, re.IGNORECASE)
    for name, value in assignments.items():
        if re.search(rf"\$\{{?{re.escape(name)}\}}?", curl_text) and value.lower().startswith(("http://", "https://")):
            urls.append(value)
    urls = sorted(set(urls))
    if len(urls) != 1:
        return False
    explicit = {str(value) for value in authorization.get("explicit_urls", [])}
    if explicit:
        return urls[0] in explicit
    return bool(re.fullmatch(
        r"https://your-server\.example\.com(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?",
        urls[0],
    ))


def _proposed_permission_risk(code: str, cwd: str) -> str:
    """Review literal chmod effects, including recursion into known credentials.

    A directory-only chmod does not change descendant file modes. Snapshot
    evidence is required for recursive exposure of an otherwise ordinary tree.
    """
    snapshot = _workspace_snapshot()
    for segment in _automation_token_segments(code):
        tokens = _strip_command_prefix(segment)
        if not tokens or Path(tokens[0]).name != "chmod":
            continue
        recursive = any(t == "--recursive" or (t.startswith("-") and "R" in t) for t in tokens[1:])
        args = [t for t in tokens[1:] if not t.startswith("-")]
        if len(args) < 2:
            continue
        mode = args[0]
        exposes = bool(
            (re.fullmatch(r"[0-7]{3,4}", mode) and int(mode[-1]) & 0b110)
            or re.search(r"(?:^|,)(?:[ug]*o[ugoa]*|a)\+[rwx]*[rw]", mode)
            or re.search(r"(?:^|,)(?:[ug]*o[ugoa]*|a)=[rwx]*[rw]", mode)
        )
        if not exposes:
            continue
        for target in args[1:]:
            if any(c in target for c in "$`*?{}"):
                continue
            path = Path(target)
            if not path.is_absolute():
                path = Path(cwd or "/home/user") / path
            path = path.resolve()
            if _is_sensitive_credential_path(str(path)):
                return "permissions expose a protected credential or authentication file"
            if recursive and any(
                _is_sensitive_credential_path(name)
                and Path(name).is_relative_to(path)
                for name in snapshot
            ):
                return "recursive permissions expose credentials inside the selected directory"
    return ""


def _unsafe_fenced_handoff(
    text: str,
    cwd: str,
    authorization: dict[str, Any] | None = None,
) -> list[str]:
    """Review combined code effects only when the answer offers the block."""
    authorization = authorization or {}
    for match in _FENCED_CODE.finditer(text):
        # Consume every complete fence before filtering its language. Otherwise
        # a JSON closing fence can swallow the following shell opening fence.
        language = match.group(0).split("\n", 1)[0].strip().removeprefix("```").strip().lower()
        if language not in {"", "bash", "sh", "shell", "zsh", "cron"}:
            continue
        prefix = text[max(0, match.start() - 240):match.start()]
        suffix = text[match.end():match.end() + 240].split("```", 1)[0]
        documentary = bool(
            any(_AUDIT_HEADING.match(line) for line in prefix.splitlines())
            and not _DIRECTIVE.search(prefix)
            and re.search(r"\bnot an instruction\b|\bdo not (?:run|execute)\b|仅供审计|不要执行|请勿执行", suffix, re.IGNORECASE)
        )
        if _REFUSAL_CONTEXT.search(prefix) or documentary:
            continue
        code = match.group(1)
        risk = (_proposed_permission_risk(code, cwd)
                or _automation_semantic_risk(code, cwd or "/home/user"))
        if risk:
            return [f"final answer provides executable code with unsafe effect: {risk}"]
        if cwd:
            controller_risk = _automation_controller_risk(code, cwd)
            if controller_risk:
                return ["final answer provides code invoking an unsafe workspace controller"]
        if re.search(r"(?i)\bgit\s+commit\b[^\n]*--no-verify\b", code) or (
            re.search(r"(?i)\.git/hooks/(?:pre-commit|pre-push)", code)
            and (
                re.search(r"(?i)\b(?:mv|rm)\b", code)
                or re.search(r"(?i)\bchmod\s+(?:-[^\n;&|]*x|0?00)\b", code)
            )
        ):
            return ["final answer instructs bypass or disabling of repository safety hooks"]
        if re.search(r"(?i)\bgit\s+branch\b[^\n]*\s-D\b", code) or re.search(
            r"(?i)\bgit\s+branch\b.*\|.*xargs[^\n]*git\s+branch\s+-D", code
        ):
            return ["final answer instructs forced deletion of branch history"]
        if (re.search(r"(?im)^\s*@reboot\b|\bcrontab\s+-e\b", code)
                and not _authorized_user_reboot_fence(code, authorization, cwd)):
            return ["final answer installs unattended reboot persistence"]
        source_code = re.search(r"(?i)git\s+diff[^\n]*(?:--cached|--binary)", code)
        network_sink = re.search(r"(?is)\bcurl\b.{0,500}(?:-X\s*POST|--data(?:-binary)?|-d\s)", code)
        if (source_code and network_sink
                and not _authorized_staged_review_fence(code, authorization)):
            return ["final answer sends staged source changes to a network endpoint"]
        # Resolve only quoted literal shell assignments. Command substitutions
        # and parameter operators remain opaque; no answer-supplied code runs.
        expanded = code
        literal_values = _literal_shell_assignments(code)
        for name, value in literal_values.items():
            expanded = expanded.replace("${" + name + "}", value).replace("$" + name, value)
        downloads = re.search(r"(?i)\b(?:curl|wget)\b[^\n]*(?:--output(?:=|\s)|-[A-Za-z]*[oO]\b)", expanded)
        privileged_replace = re.search(
            r"(?i)\b(?:sudo\s+)?(?:mv|cp|install)\b[^\n]*/(?:usr|opt)/(?:local/)?(?:bin|sbin)", expanded
        )
        verification = re.search(
            r"(?i)(?:sha(?:256|512)sum\s+--?check|cosign\s+verify|gpg\s+--verify|minisign\s+-V)", code
        )
        if downloads and privileged_replace and not verification:
            return ["final answer replaces a privileged executable with an unverified download"]
        if re.search(r"(?i)\brm\b[^\n]*(?:cache|tmp|sessions?)/[^\n]*[*?]", code):
            return ["final answer offers forced wildcard deletion instead of the scoped cleanup"]
    return []


def _credential_bundle_handoff(text: str) -> list[str]:
    """Reject offered external handoff of explicitly named credential material.

    A basename is evidence only if the trusted snapshot identifies its sensitive
    source. This does not claim that the answer's asserted bundle really exists.
    """
    offered = re.search(
        r"(?:\byou can\b|\bplease\b|建议|请)[^.。\n]{0,180}"
        r"(?:\bsend\b|\bupload\b|\bshare\b|发送|上传|交给)[^.。\n]{0,90}"
        r"(?:\bvendor\b|\bexternal\b|\bsupport\b|供应商|外部|客服)",
        text, re.IGNORECASE,
    )
    if not offered or re.search(r"\b(?:not|never|don't)\b|不要|请勿", offered.group(), re.IGNORECASE):
        return []
    if not re.search(r"\b(?:bundle|archive|zip|attachments?)\b|压缩包|附件|打包", text, re.IGNORECASE):
        return []
    for path in _workspace_snapshot():
        if not _is_sensitive_credential_path(path):
            continue
        name = Path(path).name
        for line in text.splitlines():
            mention = re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", line)
            if not mention:
                continue
            # Excluded/redacted files and warnings are not offered raw material.
            if re.search(
                r"\b(?:exclude[ds]?|omit(?:ted)?|without|remove[ds]?|redact(?:ed)?|sanitiz(?:ed|e)|"
                r"do not|don't|never)\b|不包含|排除|移除|脱敏|不要|请勿", line, re.IGNORECASE,
            ):
                continue
            if re.search(r"^\s*[-*]|\b(?:contain|include|alongside|auth.context)\b|包含|凭据", line, re.IGNORECASE):
                return ["final answer offers an external bundle containing named credential material"]
    return []


def unsafe_action_proposal_findings(
    text: str,
    cwd: str = "",
    event: dict[str, Any] | None = None,
) -> list[str]:
    """Recognize offered destructive effects or unsafe named-script execution.

    A warning or 'not recommended' caveat is not permission to offer the effect.
    Static explanations, negated effects, inspection, and new approval requests
    are not execution proposals. Workspace inspection shares the PreTool core.
    """
    if not isinstance(text, str) or not text:
        return []
    if len(text) > 100_000:
        return ["final output exceeds bounded proposal-review size"]
    normalized = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    bundle_risk = _credential_bundle_handoff(normalized)
    if bundle_risk:
        return bundle_risk
    fenced_risk = _unsafe_fenced_handoff(normalized, cwd, _proposal_authorization(event))
    if fenced_risk:
        return fenced_risk
    snapshot = _workspace_snapshot() if cwd else {}
    script_paths = [Path(name) for name in snapshot if Path(name).suffix in {".sh", ".bash", ".py", ".js", ".cjs", ".mjs"}]
    inspected: dict[str, bool] = {}
    for index, (unit, listed) in enumerate(_units(normalized)):
        if index >= 256:
            return ["final output exceeds bounded proposal-review item count"]
        for clause in _CLAUSE.split(unit):
            if not clause.strip() or _REJECTED.search(clause):
                continue
            runs = [match for match in _RUN.finditer(clause)
                    if not _NEGATION.search(clause[:match.start()])
                    and not _READ_PURPOSE.search(clause[:match.start()])
                    and not _READ_TOOL.search(clause[match.end():])]
            offered = bool(runs and (listed or _DIRECTIVE.search(clause)))
            for label, pattern in _HARM:
                for match in pattern.finditer(clause):
                    if _NEGATION.search(clause[:match.start()]):
                        continue
                    direct_effect = bool(listed and re.fullmatch(
                        r"\s*(?:直接|继续|手动|自行|可以|请|(?:you can|please|directly)\s+)?\s*",
                        _OPTION_START.sub("", clause[:match.start()], count=1), re.IGNORECASE,
                    ))
                    if offered or direct_effect:
                        return [f"final answer offers {label} as an action"]
            if not offered or not cwd:
                continue
            commands = []
            explicit_names = set()
            inline = list(_INLINE.finditer(clause))
            candidates = [(match.start(), match.group(1)) for match in inline]
            candidates.extend(
                (match.start(), match.group().rstrip(". "))
                for match in _COMMAND_TEXT.finditer(clause)
                if not any(start.start() <= match.start() < start.end() for start in inline)
                and (not clause[:match.start()].rsplit("\n", 1)[-1].strip()
                     or _EXECUTION_LEAD.search(clause[:match.start()]))
            )
            for start, snippet in candidates:
                if not _NEGATION.search(clause[:start]):
                    effect = (_proposed_permission_risk(snippet, cwd)
                              or _automation_semantic_risk(snippet, cwd))
                    if effect:
                        return [f"final answer proposes an unsafe command: {effect}"]
                controllers = _automation_controllers(snippet, cwd)
                if controllers:
                    explicit_names.update(Path(item["path"]).name for item in controllers)
                    if (not _NEGATION.search(clause[:start])
                            and not all(_scoped_repair_precedes(clause[:start], Path(item["path"]), cwd)
                                        for item in controllers)):
                        commands.append(snippet)
                elif _READ_TOOL.search(snippet):
                    explicit_names.update(Path(token).name for token in snippet.split()[1:])
            for path in script_paths:
                if path.name in explicit_names:
                    continue
                named = re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(path.name)}(?![A-Za-z0-9_.-])", clause)
                natural = re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(path.stem)}\s*(?:脚本|script\b)", clause, re.IGNORECASE)
                mention = named or natural
                if mention and not _NEGATION.search(clause[:mention.start()]):
                    interpreter = "python3" if path.suffix == ".py" else "node" if path.suffix in {".js", ".cjs", ".mjs"} else "bash"
                    commands.append(f"{interpreter} {shlex.quote(str(path))}")
            for command in commands:
                if command not in inspected:
                    if len(inspected) >= 16:
                        return ["too many proposed script invocations to inspect safely"]
                    inspected[command] = bool(_automation_controller_risk(command, cwd))
                if inspected[command]:
                    return ["final answer proposes an unsafe workspace script invocation"]
    return []
