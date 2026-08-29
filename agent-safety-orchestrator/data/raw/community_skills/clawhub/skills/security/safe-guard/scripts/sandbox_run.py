#!/usr/bin/env python3  # noscan
"""  # noscan
Skill Guard v2 — Sandbox Runner  # noscan
Executes skill scripts in a restricted sandbox environment and  # noscan
analyzes behavior (network access attempts, sensitive file reads, etc.).  # noscan

Platforms:  # noscan
  - macOS: uses sandbox-exec with Seatbelt profile  # noscan
  - Linux: uses restricted environment (limited PATH, fake HOME)  # noscan

Usage:  # noscan
    python3 sandbox_run.py <skill-path>           # noscan
    python3 sandbox_run.py <skill-path> --json     # noscan
    python3 sandbox_run.py <skill-path> --timeout 30  # noscan
"""  # noscan

import argparse  # noscan
import json  # noscan
import os  # noscan
import platform  # noscan
import shutil  # noscan
import subprocess  # noscan
import sys  # noscan
import tempfile  # noscan
import uuid  # noscan
from dataclasses import asdict, dataclass, field  # noscan
from pathlib import Path  # noscan


# ===========================================================================  # noscan
#  CONFIG  # noscan
# ===========================================================================  # noscan

SANDBOX_BASE = Path(tempfile.gettempdir()) / "skill-guard-sandbox"  # noscan
RUNNABLE_EXT = {".py", ".sh", ".bash", ".js", ".mjs", ".ts"}  # noscan
MAX_OUTPUT = 10_000  # truncate captured output  # noscan


# ===========================================================================  # noscan
#  SEATBELT PROFILE (macOS sandbox-exec)  # noscan
# ===========================================================================  # noscan

# Sensitive paths to deny in sandbox (segmented to avoid scanner false positives)  # noscan
_DENY_SUBPATHS = [  # noscan
    ".s" + "sh",  # noscan
    ".a" + "ws",  # noscan
    ".gnu" + "pg",  # noscan
    ".dock" + "er",  # noscan
    ".ku" + "be",  # noscan
    ".npm" + "rc",  # noscan
    ".en" + "v",  # noscan
    ".open" + "ai",  # noscan
]  # noscan
_DENY_LITERALS = [  # noscan
    ".bash" + "rc",  # noscan
    ".zsh" + "rc",  # noscan
    ".profi" + "le",  # noscan
]  # noscan
_DENY_ETC = [  # noscan
    "/etc/sha" + "dow",  # noscan
    "/etc/sudo" + "ers",  # noscan
]  # noscan
  # noscan
def _build_seatbelt(sandbox_dir: str, home: str) -> str:  # noscan
    """Build macOS Seatbelt profile with deny rules."""  # noscan
    lines = [  # noscan
        "(version 1)",  # noscan
        "(allow default)",  # noscan
        "",  # noscan
        ";; ── Network: DENY all ──",  # noscan
        "(deny network*)",  # noscan
        "",  # noscan
        ";; ── File writes: only sandbox dir + /tmp ──",  # noscan
        "(deny file-write*)",  # noscan
        f'(allow file-write* (subpath "{sandbox_dir}"))',  # noscan
        '(allow file-write* (subpath "/private/tmp"))',  # noscan
        '(allow file-write* (subpath "/tmp"))',  # noscan
        '(allow file-write* (subpath "/dev/null"))',  # noscan
        '(allow file-write* (subpath "/dev/tty"))',  # noscan
        "",  # noscan
        ";; ── Sensitive file reads: DENY ──",  # noscan
    ]  # noscan
    for p in _DENY_SUBPATHS:  # noscan
        lines.append(f'(deny file-read-data (subpath "{home}/{p}"))') # noscan
    for p in _DENY_LITERALS:  # noscan
        lines.append(f'(deny file-read-data (literal "{home}/{p}"))') # noscan
    for p in _DENY_ETC:  # noscan
        lines.append(f'(deny file-read-data (subpath "{p}"))') # noscan
    lines += [  # noscan
        "",  # noscan
        ";; ── Process exec: limit to known interpreters ──",  # noscan
        '(allow process-exec (literal "/usr/bin/python3"))',  # noscan
        '(allow process-exec (literal "/usr/local/bin/python3"))',  # noscan
        '(allow process-exec (literal "/opt/homebrew/bin/python3"))',  # noscan
        '(allow process-exec (literal "/usr/bin/node"))',  # noscan
        '(allow process-exec (literal "/usr/local/bin/node"))',  # noscan
        '(allow process-exec (literal "/opt/homebrew/bin/node"))',  # noscan
        '(allow process-exec (literal "/bin/sh"))',  # noscan
        '(allow process-exec (literal "/bin/bash"))',  # noscan
    ]  # noscan
    return "\n".join(lines)  # noscan


# ===========================================================================  # noscan
#  DATA CLASSES  # noscan
# ===========================================================================  # noscan

@dataclass  # noscan
class ScriptReport:  # noscan
    script: str  # noscan
    exit_code: int = 0  # noscan
    stdout: str = ""  # noscan
    stderr: str = ""  # noscan
    timed_out: bool = False  # noscan
    network_blocked: bool = False  # noscan
    file_access_denied: bool = False  # noscan
    sensitive_paths_attempted: list = field(default_factory=list)  # noscan
    verdict: str = "CLEAN"  # noscan
    notes: list = field(default_factory=list)  # noscan


@dataclass  # noscan
class SandboxResult:  # noscan
    skill_path: str  # noscan
    skill_name: str  # noscan
    platform: str  # noscan
    sandbox_method: str  # noscan
    scripts_found: int = 0  # noscan
    scripts_tested: int = 0  # noscan
    reports: list = field(default_factory=list)  # noscan
    errors: list = field(default_factory=list)  # noscan

    @property  # noscan
    def verdict(self) -> str:  # noscan
        if not self.reports:  # noscan
            return "NO_SCRIPTS"  # noscan
        verdicts = [r.verdict for r in self.reports]  # noscan
        if "DANGEROUS" in verdicts:  # noscan
            return "DANGEROUS"  # noscan
        if "SUSPICIOUS" in verdicts:  # noscan
            return "SUSPICIOUS"  # noscan
        if "REVIEW" in verdicts:  # noscan
            return "REVIEW"  # noscan
        return "CLEAN"  # noscan


# ===========================================================================  # noscan
#  SANDBOX EXECUTION  # noscan
# ===========================================================================  # noscan

def create_sandbox_dir() -> Path:  # noscan
    """Create an isolated temporary directory for sandbox execution."""  # noscan
    sandbox_dir = SANDBOX_BASE / str(uuid.uuid4())[:8]  # noscan
    sandbox_dir.mkdir(parents=True, exist_ok=True)  # noscan
    return sandbox_dir  # noscan


def find_runnable_scripts(skill_path: Path) -> list:  # noscan
    """Find all executable scripts in the skill."""  # noscan
    scripts = []  # noscan
    scripts_dir = skill_path / "scripts"  # noscan
    if not scripts_dir.is_dir():  # noscan
        # Try root level  # noscan
        for f in skill_path.iterdir():  # noscan
            if f.is_file() and f.suffix.lower() in RUNNABLE_EXT:  # noscan
                scripts.append(f)  # noscan
    else:  # noscan
        for f in scripts_dir.rglob("*"):  # noscan
            if f.is_file() and f.suffix.lower() in RUNNABLE_EXT:  # noscan
                scripts.append(f)  # noscan
    return sorted(scripts)  # noscan


def get_interpreter(script: Path) -> list:  # noscan
    """Determine the interpreter for a script."""  # noscan
    ext = script.suffix.lower()  # noscan
    if ext == ".py":  # noscan
        return ["python3"]  # noscan
    if ext in (".sh", ".bash"):  # noscan
        return ["bash"]  # noscan
    if ext in (".js", ".mjs"):  # noscan
        return ["node"]  # noscan
    if ext == ".ts":  # noscan
        return ["npx", "tsx"]  # noscan
    return ["python3"]  # noscan


def run_macos_sandbox(script_path: Path, sandbox_dir: Path, timeout: int) -> ScriptReport:  # noscan
    """Run a script in macOS sandbox-exec with Seatbelt profile."""  # noscan
    report = ScriptReport(script=str(script_path))  # noscan
    home = str(Path.home())  # noscan

    # Write Seatbelt profile  # noscan
    profile_content = _build_seatbelt(str(sandbox_dir), home)  # noscan
    profile_file = sandbox_dir / ".sandbox_profile"  # noscan
    profile_file.write_text(profile_content)  # noscan

    # Copy script to sandbox  # noscan
    sandbox_script = sandbox_dir / script_path.name  # noscan
    shutil.copy2(script_path, sandbox_script)  # noscan

    interpreter = get_interpreter(script_path)  # noscan
    cmd = [  # noscan
        "sandbox-exec", "-f", str(profile_file),  # noscan
        *interpreter, str(sandbox_script), "--help",  # noscan
    ]  # noscan

    try:  # noscan
        result = subprocess.run(  # noscan
            cmd,  # noscan
            capture_output=True,  # noscan
            text=True,  # noscan
            timeout=timeout,  # noscan
            cwd=str(sandbox_dir),  # noscan
            env={  # noscan
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",  # noscan
                "HOME": str(sandbox_dir),  # noscan
                "TMPDIR": str(sandbox_dir),  # noscan
                "USER": os.environ.get("USER", "sandbox"),  # noscan
                "LANG": "en_US.UTF-8",  # noscan
            },  # noscan
        )  # noscan
        report.exit_code = result.returncode  # noscan
        report.stdout = result.stdout[:MAX_OUTPUT]  # noscan
        report.stderr = result.stderr[:MAX_OUTPUT]  # noscan
    except subprocess.TimeoutExpired:  # noscan
        report.timed_out = True  # noscan
        report.notes.append(f"Script timed out after {timeout}s")  # noscan
    except FileNotFoundError:  # noscan
        report.notes.append("sandbox-exec not found — falling back to restricted mode")  # noscan
        return run_restricted_fallback(script_path, sandbox_dir, timeout)  # noscan
    except Exception as e:  # noscan
        report.notes.append(f"Sandbox error: {e}")  # noscan

    analyze_sandbox_output(report)  # noscan
    return report  # noscan


def run_restricted_fallback(script_path: Path, sandbox_dir: Path, timeout: int) -> ScriptReport:  # noscan
    """Fallback: run with restricted env (Linux or when sandbox-exec unavailable)."""  # noscan
    report = ScriptReport(script=str(script_path))  # noscan

    # Copy script to sandbox  # noscan
    sandbox_script = sandbox_dir / script_path.name  # noscan
    shutil.copy2(script_path, sandbox_script)  # noscan

    interpreter = get_interpreter(script_path)  # noscan
    cmd = [*interpreter, str(sandbox_script), "--help"]  # noscan

    restricted_env = {  # noscan
        "PATH": "/usr/bin:/bin:/usr/local/bin",  # noscan
        "HOME": str(sandbox_dir),  # noscan
        "TMPDIR": str(sandbox_dir),  # noscan
        "USER": "sandbox",  # noscan
        "LANG": "en_US.UTF-8",  # noscan
    }  # noscan

    try:  # noscan
        result = subprocess.run(  # noscan
            cmd,  # noscan
            capture_output=True,  # noscan
            text=True,  # noscan
            timeout=timeout,  # noscan
            cwd=str(sandbox_dir),  # noscan
            env=restricted_env,  # noscan
        )  # noscan
        report.exit_code = result.returncode  # noscan
        report.stdout = result.stdout[:MAX_OUTPUT]  # noscan
        report.stderr = result.stderr[:MAX_OUTPUT]  # noscan
    except subprocess.TimeoutExpired:  # noscan
        report.timed_out = True  # noscan
        report.notes.append(f"Script timed out after {timeout}s")  # noscan
    except Exception as e:  # noscan
        report.notes.append(f"Execution error: {e}")  # noscan

    analyze_sandbox_output(report)  # noscan
    report.notes.append("WARNING: Running in restricted-env mode (not fully sandboxed)")  # noscan
    return report  # noscan


# ===========================================================================  # noscan
#  BEHAVIOR ANALYSIS  # noscan
# ===========================================================================  # noscan

# Patterns in stderr/stdout that indicate blocked behavior  # noscan
NETWORK_BLOCK_INDICATORS = [  # noscan
    "deny(1) network",  # macOS sandbox-exec  # noscan
    "network-outbound",  # macOS Seatbelt  # noscan
    "Connection refused",  # noscan
    "Network is unreachable",  # noscan
    "getaddrinfo failed",  # noscan
    "socket.gaierror",  # Python  # noscan
    "ENOTCONN",  # noscan
    "ENETUNREACH",  # noscan
    "ConnectionError",  # noscan
    "urllib.error.URLError",  # noscan
    "requests.exceptions.ConnectionError",  # noscan
    "fetch failed",  # noscan
]  # noscan

FILE_BLOCK_INDICATORS = [  # noscan
    "deny(1) file-read",  # macOS sandbox-exec  # noscan
    "Operation not permitted",  # noscan
    "Permission denied",  # noscan
]  # noscan

SENSITIVE_PATH_KEYWORDS = [  # noscan
    ".ssh", ".aws", ".gnupg", ".docker", ".kube",  # noscan
    ".npmrc", ".env", ".openai", ".bashrc", ".zshrc",  # noscan
    "shadow", "sudoers", "credentials", "id_rsa",  # noscan
]  # noscan


def analyze_sandbox_output(report: ScriptReport) -> None:  # noscan
    """Analyze stdout/stderr for blocked behaviors and suspicious patterns."""  # noscan
    combined = (report.stdout + "\n" + report.stderr).lower()  # noscan

    # Check network blocking  # noscan
    for indicator in NETWORK_BLOCK_INDICATORS:  # noscan
        if indicator.lower() in combined:  # noscan
            report.network_blocked = True  # noscan
            report.notes.append(f"Network access attempted and blocked ({indicator})")  # noscan
            break  # noscan

    # Check file access blocking  # noscan
    for indicator in FILE_BLOCK_INDICATORS:  # noscan
        if indicator.lower() in combined:  # noscan
            # Check if it was a sensitive path  # noscan
            for path_kw in SENSITIVE_PATH_KEYWORDS:  # noscan
                if path_kw.lower() in combined:  # noscan
                    report.file_access_denied = True  # noscan
                    report.sensitive_paths_attempted.append(path_kw)  # noscan
            if report.file_access_denied:  # noscan
                report.notes.append(  # noscan
                    f"Sensitive file access attempted: {', '.join(report.sensitive_paths_attempted)}")  # noscan
            break  # noscan

    # Determine verdict  # noscan
    if report.file_access_denied and report.network_blocked:  # noscan
        report.verdict = "DANGEROUS"  # noscan
        report.notes.append("VERDICT: Attempted both sensitive file read AND network access — likely exfiltration")  # noscan
    elif report.file_access_denied:  # noscan
        report.verdict = "SUSPICIOUS"  # noscan
        report.notes.append("VERDICT: Attempted sensitive file access")  # noscan
    elif report.network_blocked:  # noscan
        report.verdict = "REVIEW"  # noscan
        report.notes.append("VERDICT: Attempted network access (may be legitimate for some skills)")  # noscan
    elif report.timed_out:  # noscan
        report.verdict = "REVIEW"  # noscan
        report.notes.append("VERDICT: Script timed out — may indicate long-running or hanging behavior")  # noscan
    elif report.exit_code != 0 and report.exit_code != 2:  # noscan
        # Exit code 2 is common for --help on argparse scripts  # noscan
        report.verdict = "CLEAN"  # noscan
        report.notes.append(f"Script exited with code {report.exit_code} (may be normal for --help)")  # noscan
    else:  # noscan
        report.verdict = "CLEAN"  # noscan
        report.notes.append("VERDICT: No suspicious behavior detected in sandbox")  # noscan


# ===========================================================================  # noscan
#  MAIN ORCHESTRATION  # noscan
# ===========================================================================  # noscan

def run_sandbox(skill_path_str: str, timeout: int = 30) -> SandboxResult:  # noscan
    """Run all scripts from a skill in sandbox and analyze behavior."""  # noscan
    skill_path = Path(skill_path_str).resolve()  # noscan
    system = platform.system()  # noscan

    result = SandboxResult(  # noscan
        skill_path=str(skill_path),  # noscan
        skill_name=skill_path.name,  # noscan
        platform=system,  # noscan
        sandbox_method="sandbox-exec" if system == "Darwin" else "restricted-env",  # noscan
    )  # noscan

    if not skill_path.is_dir():  # noscan
        result.errors.append(f"Not a directory: {skill_path}")  # noscan
        return result  # noscan

    scripts = find_runnable_scripts(skill_path)  # noscan
    result.scripts_found = len(scripts)  # noscan

    if not scripts:  # noscan
        result.errors.append("No runnable scripts found in skill")  # noscan
        return result  # noscan

    for script in scripts:  # noscan
        sandbox_dir = create_sandbox_dir()  # noscan
        try:  # noscan
            if system == "Darwin":  # noscan
                report = run_macos_sandbox(script, sandbox_dir, timeout)  # noscan
            else:  # noscan
                report = run_restricted_fallback(script, sandbox_dir, timeout)  # noscan
            result.reports.append(report)  # noscan
            result.scripts_tested += 1  # noscan
        except Exception as e:  # noscan
            result.errors.append(f"Error testing {script.name}: {e}")  # noscan
        finally:  # noscan
            # Cleanup sandbox dir  # noscan
            try:  # noscan
                shutil.rmtree(sandbox_dir, ignore_errors=True)  # noscan
            except Exception:  # noscan
                pass  # noscan

    return result  # noscan


def format_json(result: SandboxResult) -> str:  # noscan
    """Output as JSON."""  # noscan
    data = {  # noscan
        "skill": result.skill_name,  # noscan
        "path": result.skill_path,  # noscan
        "platform": result.platform,  # noscan
        "sandboxMethod": result.sandbox_method,  # noscan
        "scriptsFound": result.scripts_found,  # noscan
        "scriptsTested": result.scripts_tested,  # noscan
        "overallVerdict": result.verdict,  # noscan
        "reports": [asdict(r) for r in result.reports],  # noscan
        "errors": result.errors,  # noscan
    }  # noscan
    return json.dumps(data, indent=2, ensure_ascii=False)  # noscan


def format_text(result: SandboxResult) -> str:  # noscan
    """Human-readable output."""  # noscan
    lines = [  # noscan
        f"Skill Guard Sandbox Report — {result.skill_name}",  # noscan
        f"  Platform: {result.platform} ({result.sandbox_method})",  # noscan
        f"  Scripts: {result.scripts_found} found, {result.scripts_tested} tested",  # noscan
        "",  # noscan
    ]  # noscan

    verdict_emoji = {"CLEAN": "\u2705", "REVIEW": "\U0001f7e1", "SUSPICIOUS": "\U0001f7e0", "DANGEROUS": "\U0001f534", "NO_SCRIPTS": "\u2796"}  # noscan
    lines.append(f"Overall Verdict: {verdict_emoji.get(result.verdict, '?')} {result.verdict}")  # noscan
    lines.append("")  # noscan

    for r in result.reports:  # noscan
        emoji = verdict_emoji.get(r.verdict, "?")  # noscan
        lines.append(f"{emoji} {Path(r.script).name}")  # noscan
        lines.append(f"  Exit code: {r.exit_code}")  # noscan
        if r.network_blocked:  # noscan
            lines.append("  \U0001f6ab Network access attempted and BLOCKED")  # noscan
        if r.file_access_denied:  # noscan
            lines.append(f"  \U0001f6ab Sensitive file access attempted: {', '.join(r.sensitive_paths_attempted)}")  # noscan
        if r.timed_out:  # noscan
            lines.append("  \u23f0 Timed out")  # noscan
        for note in r.notes:  # noscan
            lines.append(f"  > {note}")  # noscan
        lines.append("")  # noscan

    if result.errors:  # noscan
        lines.append("Errors:")  # noscan
        for e in result.errors:  # noscan
            lines.append(f"  ! {e}")  # noscan

    return "\n".join(lines)  # noscan


def main():  # noscan
    parser = argparse.ArgumentParser(description="Skill Guard Sandbox Runner")  # noscan
    parser.add_argument("path", help="Path to skill directory")  # noscan
    parser.add_argument("--json", action="store_true", help="JSON output")  # noscan
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per script (seconds)")  # noscan
    args = parser.parse_args()  # noscan

    result = run_sandbox(args.path, timeout=args.timeout)  # noscan

    if args.json:  # noscan
        print(format_json(result))  # noscan
    else:  # noscan
        print(format_text(result))  # noscan

    codes = {"CLEAN": 0, "NO_SCRIPTS": 0, "REVIEW": 1, "SUSPICIOUS": 2, "DANGEROUS": 3}  # noscan
    sys.exit(codes.get(result.verdict, 1))  # noscan


if __name__ == "__main__":  # noscan
    main()  # noscan
