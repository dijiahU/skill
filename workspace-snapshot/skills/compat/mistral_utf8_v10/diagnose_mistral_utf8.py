#!/usr/bin/env python3
"""CPU-only reproduction and regression for SABER Mistral UTF-8 compatibility."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

DEFAULT_MODEL = Path(
    "/2024233123/skills/models/modelscope/mistralai/"
    "Mistral-Small-4-119B-2603"
)
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def stream_decode(tokenizer, prompt_ids, output_ids, prompt_fn, incremental_fn):
    tokens, prefix_offset, read_offset = prompt_fn(
        tokenizer, prompt_ids, skip_special_tokens=False
    )
    all_ids = list(prompt_ids)
    text = ""
    for token_id in output_ids:
        all_ids.append(token_id)
        new_tokens, delta, prefix_offset, read_offset = incremental_fn(
            tokenizer,
            all_ids,
            tokens,
            prefix_offset,
            read_offset,
            skip_special_tokens=False,
            spaces_between_special_tokens=True,
        )
        tokens.extend(new_tokens)
        text += delta
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    from mistral_common.tokens.tokenizers.base import SpecialTokens
    from vllm.tokenizers.mistral import MistralTokenizer
    import vllm.tokenizers.detokenizer_utils as utils
    import vllm.v1.engine.detokenizer as engine_detokenizer

    tokenizer = MistralTokenizer.from_pretrained(str(args.model))
    original_class_method = MistralTokenizer.convert_ids_to_tokens
    original_prompt = utils.convert_prompt_ids_to_tokens
    original_incremental = utils.detokenize_incrementally
    vocab_key_types_before = sorted(
        {type(key).__name__ for key in tokenizer.get_vocab().keys()}
    )

    cases = {
        "chinese": "让我检查系统的防火墙服务状态。",
        "mixed_ascii": "中文、多字节 UTF-8: check 配置与权限。",
        "emoji": "✅ 安全检查完成 🔒",
        "database": "数据库优化建议：备份、日志、缓存。",
        "ascii": "plain ASCII command: printf ok",
        "literal_replacement": "literal � marker 与中文",
    }
    prompt_ids = tokenizer.encode("工具调用上下文：", add_special_tokens=False)

    baseline = {}
    encoded = {}
    for name, source in cases.items():
        ids = tokenizer.encode(source, add_special_tokens=False)
        encoded[name] = ids
        batch = tokenizer.decode(ids, skip_special_tokens=False)
        streamed = stream_decode(
            tokenizer, prompt_ids, ids, original_prompt, original_incremental
        )
        baseline[name] = {
            "source": source,
            "batch": batch,
            "incremental": streamed,
            "replacement_count": streamed.count("�"),
            "equal_to_batch": streamed == batch,
        }

    os.environ["SABER_MISTRAL_UTF8_COMPAT_V10"] = "1"
    from mistral_utf8_compat import PATCH_VERSION, install

    installed_first = install()
    installed_second = install()

    patched = {}
    for name, source in cases.items():
        ids = encoded[name]
        batch = tokenizer.decode(ids, skip_special_tokens=False)
        streamed = stream_decode(
            tokenizer,
            prompt_ids,
            ids,
            utils.convert_prompt_ids_to_tokens,
            utils.detokenize_incrementally,
        )
        patched[name] = {
            "source": source,
            "batch": batch,
            "incremental": streamed,
            "replacement_count": streamed.count("�"),
            "equal_to_batch": streamed == batch,
        }

    tool_object = {
        "name": "saber_bash",
        "arguments": {
            "command": "python3 -c 'print(\"中文 ✅ 🔒\")'",
            "note": "保留 JSON 与 ASCII 123",
        },
    }
    tool_json = json.dumps(tool_object, ensure_ascii=False, separators=(",", ":"))
    tool_ids = tokenizer.encode(tool_json, add_special_tokens=False)
    tool_stream = stream_decode(
        tokenizer,
        prompt_ids,
        tool_ids,
        utils.convert_prompt_ids_to_tokens,
        utils.detokenize_incrementally,
    )
    tool_json_ok = json.loads(tool_stream) == tool_object

    tool_marker_id = tokenizer.tokenizer.get_special_token(SpecialTokens.tool_calls)
    framed_ids = [tool_marker_id] + tool_ids
    framed_batch = tokenizer.decode(framed_ids, skip_special_tokens=False)
    framed_stream = stream_decode(
        tokenizer,
        prompt_ids,
        framed_ids,
        utils.convert_prompt_ids_to_tokens,
        utils.detokenize_incrementally,
    )

    vocab_key_types_after = sorted(
        {type(key).__name__ for key in tokenizer.get_vocab().keys()}
    )
    result = {
        "patch_version": PATCH_VERSION,
        "python": sys.version,
        "model_path": str(args.model),
        "model_tokenizer_files_sha256": {
            name: hashlib.sha256((args.model / name).read_bytes()).hexdigest()
            for name in ("tekken.json", "tokenizer.json")
            if (args.model / name).is_file()
        },
        "install": {
            "first": installed_first,
            "second_idempotent": not installed_second,
            "engine_reference_patched": (
                engine_detokenizer.detokenize_incrementally
                is utils.detokenize_incrementally
            ),
            "tokenizer_class_unchanged": (
                MistralTokenizer.convert_ids_to_tokens is original_class_method
            ),
            "vocab_key_types_unchanged": (
                vocab_key_types_before == vocab_key_types_after
            ),
            "vocab_key_types": vocab_key_types_after,
        },
        "baseline": baseline,
        "patched": patched,
        "tool_json": {
            "batch": tokenizer.decode(tool_ids, skip_special_tokens=False),
            "incremental": tool_stream,
            "exact_and_parseable": (
                tool_stream
                == tokenizer.decode(tool_ids, skip_special_tokens=False)
                and tool_json_ok
            ),
            "framed_batch": framed_batch,
            "framed_incremental": framed_stream,
            "framed_exact": framed_stream == framed_batch,
            "tool_marker_id": tool_marker_id,
        },
    }
    checks = {
        "baseline_reproduces": (
            not baseline["chinese"]["equal_to_batch"]
            and baseline["chinese"]["replacement_count"] > 0
        ),
        "all_patched_equal_batch": all(
            item["equal_to_batch"] for item in patched.values()
        ),
        "literal_replacement_preserved": (
            patched["literal_replacement"]["incremental"].count("�")
            == patched["literal_replacement"]["batch"].count("�")
            == 1
        ),
        "tool_json_exact_and_parseable": result["tool_json"]["exact_and_parseable"],
        "tool_marker_preserved": result["tool_json"]["framed_exact"],
        "patch_scoped": all(result["install"].values()),
    }
    result["checks"] = checks
    result["passed"] = all(checks.values())

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
