# Mistral UTF-8 compatibility for SABER v10

This opt-in process-local patch repairs vLLM 0.25 slow incremental decoding for
the Mistral Tekken tokenizer when tool parsing sets
`skip_special_tokens=False`. It does not edit vLLM, mistral-common, the old
sitecustomize module, or tokenizer vocabulary construction.

Enable it only for the Mistral vLLM service by setting:

- `PYTHONPATH=/2024233123/skills/compat/mistral_utf8_v10`
- `SABER_MISTRAL_DEVELOPER_ROLE_COMPAT=1`
- `SABER_MISTRAL_UTF8_COMPAT_V10=1`
- `SABER_MISTRAL_TOOL_STRICT_COMPAT_V10=1`

The entry point also loads the existing developer-role shim when its flag is
set and raises if that sibling file is missing. Because Python may log and continue
after a sitecustomize import failure, the service launcher must run this gate under
the exact service environment before starting vLLM:

    /2024233123/skills/envs/deepseekv4-vllm/bin/python \
      /2024233123/skills/compat/mistral_utf8_v10/verify_activation.py

Start vLLM only when the probe exits 0. The patch wraps only vLLM slow incremental prompt/token conversion. For a
Tekken Mistral tokenizer with `skip_special_tokens=False`, ordinary token
pieces stay as bytes until the existing tokenizer can join and decode adjacent
UTF-8 pieces. Special token strings remain visible for the Mistral tool parser.

Run the CPU-only regression:

    /2024233123/skills/envs/deepseekv4-vllm/bin/python \
      /2024233123/skills/compat/mistral_utf8_v10/diagnose_mistral_utf8.py

Success requires exact equality with batch decode for Chinese, emoji, mixed
ASCII, tool JSON, and a literal replacement-character case. The last case
proves the patch does not filter U+FFFD.


The separate tool-strict patch treats Responses `strict=None` as unspecified
before Mistral validation. It preserves explicit `strict=False` and
`strict=True`. Validate the real vLLM Responses construction path with:

    /2024233123/skills/envs/deepseekv4-vllm/bin/python \
      /2024233123/skills/compat/mistral_utf8_v10/diagnose_mistral_tool_strict.py
