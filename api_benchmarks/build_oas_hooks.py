"""Build the existing OAS SDK hook compatibility layer with its source digest."""

import subprocess
import shutil
import tempfile
from pathlib import Path

from benchmarks.openagentsafety.build_images import get_image_name
from benchmarks.openagentsafety.safety_orchestrator import hook_adapter_digest


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "openagentsafety"
    base = get_image_name()
    # The upstream .dockerignore excludes vendor/. Supply only the Dockerfile
    # and the three required sources in a temporary build context.
    with tempfile.TemporaryDirectory(prefix="oas-hooks-build-") as temporary:
        context = Path(temporary)
        dockerfile = context / "Dockerfile"
        shutil.copyfile(
            root / "benchmarks/openagentsafety/Dockerfile.safety-hooks", dockerfile
        )
        relative = Path("vendor/software-agent-sdk/openhands-sdk/openhands/sdk")
        for name in (
            "hooks/executor.py",
            "hooks/conversation_hooks.py",
            "tool/builtins/invoke_skill.py",
        ):
            target = context / relative / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative / name, target)
        subprocess.run(
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "--build-arg",
                f"BASE_IMAGE={base}",
                "--build-arg",
                f"HOOKS_SHA256={hook_adapter_digest()}",
                "-f",
                str(dockerfile),
                "-t",
                f"{base}-oas-hooks-v1",
                str(context),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
