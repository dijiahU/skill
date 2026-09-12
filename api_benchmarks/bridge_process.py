"""Manage the local protocol bridge for a bounded benchmark run."""

from contextlib import contextmanager
import json
import secrets
import socket
import subprocess
import time
import urllib.request


@contextmanager
def chat_bridge(env, cfg, python, root, output):
    """Start an authenticated bridge and always terminate it after the run."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    token = secrets.token_urlsafe(32)
    child = dict(
        env,
        BRIDGE_TOKEN=token,
        BRIDGE_MODEL=cfg["id"],
        BRIDGE_UPSTREAM_URL=cfg["base_url"],
        BRIDGE_UPSTREAM_KEY=cfg["key"],
        BRIDGE_LOG=str(output / "bridge-requests.jsonl"),
    )
    output.mkdir(parents=True, exist_ok=True)
    with (output / "bridge-process.log").open("a") as log:
        process = subprocess.Popen(
            [python, "-m", "api_benchmarks.responses_bridge", "--port", str(port)],
            cwd=root,
            env=child,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(
                        "Responses bridge exited; inspect bridge-process.log"
                    )
                try:
                    with opener.open(
                        f"http://127.0.0.1:{port}/health", timeout=1
                    ) as response:
                        if json.load(response)["status"] == "ready":
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Responses bridge did not become ready")
            yield {
                "OPENAI_API_KEY": token,
                "OPENAI_BASE_URL": f"http://host.docker.internal:{port}/v1",
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
