"""Authenticated local Responses-to-Chat bridge for the existing Codex harness.

Run with the Harbor environment. Provider credentials stay in this host process;
task containers receive only an ephemeral bridge token. No prompts are logged.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import time

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import uvicorn


def create_app(settings: dict[str, str]) -> FastAPI:
    """Expose a fixed upstream model, never a user-selected URL or credential."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
    token = settings["BRIDGE_TOKEN"]
    model = settings["BRIDGE_MODEL"]
    log = Path(settings["BRIDGE_LOG"])

    def record(data: dict) -> None:
        with log.open("a") as stream:
            stream.write(json.dumps({"time": time.time(), **data}) + "\n")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ready", "model": model}

    @app.post("/v1/responses")
    async def responses(request: Request):
        if not hmac.compare_digest(
            request.headers.get("authorization", ""), f"Bearer {token}"
        ):
            raise HTTPException(401, "Invalid bridge token")
        body = await request.json()
        if body.get("model") != model:
            raise HTTPException(400, "Model differs from the fixed benchmark model")
        if body.get("previous_response_id"):
            raise HTTPException(400, "Send full history; this bridge is stateless")
        if not body.get("stream"):
            raise HTTPException(400, "This benchmark bridge requires streaming")
        params = {
            key: body[key]
            for key in (
                "input",
                "instructions",
                "tools",
                "tool_choice",
                "parallel_tool_calls",
            )
            if key in body
        }
        # LiteLLM mutates named choices into Chat format before constructing its
        # Responses events. A singleton required tool preserves the same choice.
        choice = params.get("tool_choice")
        if isinstance(choice, dict) and choice.get("type") in ("function", "custom"):
            params["tools"] = [
                tool
                for tool in params.get("tools", [])
                if tool.get("name") == choice.get("name")
            ]
            if not params["tools"]:
                raise HTTPException(400, "Named tool is absent")
            params["tool_choice"] = "required"
        started = time.monotonic()
        record(
            {
                "event": "request",
                "model": model,
                "input_items": len(body.get("input", [])),
                "tool_types": [tool.get("type") for tool in body.get("tools", [])],
            }
        )
        try:
            result = await litellm.aresponses(
                model=f"openai/{model}",
                api_base=settings["BRIDGE_UPSTREAM_URL"],
                api_key=settings["BRIDGE_UPSTREAM_KEY"],
                use_chat_completions_api=True,
                stream=True,
                max_output_tokens=int(settings.get("BRIDGE_MAX_OUTPUT_TOKENS", "8192")),
                extra_body={"enable_thinking": False},
                timeout=180,
                num_retries=1,
                **params,
            )
        except Exception as exc:
            record(
                {
                    "event": "error",
                    "error_type": type(exc).__name__,
                    "status": getattr(exc, "status_code", None),
                }
            )
            raise HTTPException(
                502, f"Upstream request failed: {type(exc).__name__}"
            ) from None

        async def events():
            try:
                async for event in result:
                    data = (
                        event.model_dump(exclude_none=True)
                        if hasattr(event, "model_dump")
                        else event
                    )
                    if data.get("type") == "response.completed":
                        response = data["response"]
                        record(
                            {
                                "event": "completed",
                                "elapsed_sec": round(time.monotonic() - started, 3),
                                "status": response.get("status"),
                                "usage": response.get("usage"),
                                "output_types": [
                                    item.get("type")
                                    for item in response.get("output", [])
                                ],
                            }
                        )
                    yield f"event: {data['type']}\ndata: {json.dumps(data)}\n\n"
            except Exception as exc:
                details = (
                    exc.errors(include_input=False, include_url=False)
                    if hasattr(exc, "errors")
                    else None
                )
                record(
                    {
                        "event": "stream_error",
                        "error_type": type(exc).__name__,
                        "validation": details,
                    }
                )
                data = {
                    "type": "response.failed",
                    "response": {
                        "status": "failed",
                        "error": {
                            "code": "bridge_stream_error",
                            "message": type(exc).__name__,
                        },
                    },
                }
                yield f"event: response.failed\ndata: {json.dumps(data)}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    uvicorn.run(
        create_app(dict(os.environ)),
        host="0.0.0.0",
        port=args.port,
        access_log=False,
        log_level="error",
    )
