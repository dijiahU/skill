"""Exercise the installed Harbor API with a fake task environment, no models."""

import json
import os
from pathlib import Path
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from api_benchmarks.harbor_codex import SafetyCodex
from harbor.models.agent.context import AgentContext


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_package_rejects_unsafe_entries_before_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "codex.tgz"
            with tarfile.open(archive, "w:gz") as output:
                output.addfile(tarfile.TarInfo("../../outside"))
            agent = SafetyCodex(
                logs_dir=Path(temporary), codex_archive=str(archive), version="0.149.1"
            )
            environment = SimpleNamespace(upload_file=AsyncMock())
            with self.assertRaisesRegex(ValueError, "Unsafe entry"):
                await agent.install(environment)
            environment.upload_file.assert_not_awaited()

    async def test_native_package_must_match_pinned_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "codex.tgz"
            with tarfile.open(archive, "w:gz"):
                pass
            agent = SafetyCodex(
                logs_dir=Path(temporary), codex_archive=str(archive), version="0.149.1"
            )
            agent.exec_as_root = AsyncMock()
            agent._installed_codex_satisfies_version = AsyncMock(return_value=False)
            environment = SimpleNamespace(upload_file=AsyncMock())
            with self.assertRaisesRegex(ValueError, "pinned version"):
                await agent.install(environment)

    async def test_conditions_preserve_exact_model_and_api_only_auth(self) -> None:
        for mode in ("none", "safety-orchestrator"):
            with tempfile.TemporaryDirectory() as temporary:
                agent = SafetyCodex(
                    logs_dir=Path(temporary),
                    model_name="org/model;literal",
                    skill_mode=mode,
                    version="0.149.1",
                )
                agent.exec_as_agent = AsyncMock(
                    return_value=SimpleNamespace(return_code=0)
                )
                agent._upload_config_text = AsyncMock()
                with patch.dict(
                    os.environ,
                    {
                        "OPENAI_API_KEY": "unit-test-secret",
                        "OPENAI_BASE_URL": "https://example.org/v1",
                    },
                    clear=True,
                ):
                    await agent.run("Print hello", SimpleNamespace(), AgentContext())
                commands = [
                    call.kwargs["command"]
                    for call in agent.exec_as_agent.call_args_list
                ]
                config = agent._upload_config_text.call_args.kwargs["content"]
                self.assertNotIn("unit-test-secret", config)
                self.assertIn('env_key = "OPENAI_API_KEY"', config)
                joined = "\n".join(commands)
                self.assertNotIn("auth.json", joined)
                self.assertIn("--model 'org/model;literal'", joined)
                self.assertEqual(
                    "--dangerously-bypass-hook-trust" in joined,
                    mode == "safety-orchestrator",
                )
                self.assertEqual(
                    "adapters/codex/install.sh" in joined, mode == "safety-orchestrator"
                )
                metadata = json.loads(
                    (Path(temporary) / "safety-condition.json").read_text()
                )
                self.assertEqual(
                    metadata["hooks_enabled"], mode == "safety-orchestrator"
                )

    async def test_agent_failure_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            agent = SafetyCodex(logs_dir=Path(temporary), model_name="test")
            agent.exec_as_agent = AsyncMock(
                side_effect=[
                    SimpleNamespace(return_code=0),
                    SimpleNamespace(return_code=7),
                    SimpleNamespace(return_code=0),
                ]
            )
            agent._upload_config_text = AsyncMock()
            with patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test", "OPENAI_BASE_URL": "https://example.org"},
                clear=True,
            ):
                with self.assertRaisesRegex(RuntimeError, "status 7"):
                    await agent.run("Hello", SimpleNamespace(), AgentContext())
            self.assertIn("sessions", agent.exec_as_agent.call_args.kwargs["command"])


if __name__ == "__main__":
    unittest.main()
