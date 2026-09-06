"""Opt-in repair for vLLM slow incremental Tekken detokenization.

This module does not modify the tokenizer class or installed packages. It wraps
only the slow incremental-detokenization entry points so Tekken byte fallback
pieces remain bytes until adjacent pieces can be decoded together.
"""
from __future__ import annotations

import os
from functools import wraps
from typing import Any

ENV_FLAG = "SABER_MISTRAL_UTF8_COMPAT_V10"
PATCH_VERSION = "saber-mistral-utf8-v10.0"


def _enabled() -> bool:
    return os.environ.get(ENV_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_affected_tokenizer(tokenizer: Any) -> bool:
    cls = type(tokenizer)
    return (
        cls.__name__ == "MistralTokenizer"
        and cls.__module__ == "vllm.tokenizers.mistral"
        and bool(getattr(tokenizer, "is_tekken", False))
    )


class _TekkenByteFallbackView:
    """Narrow tokenizer view used only by incremental detokenization."""

    def __init__(self, tokenizer: Any):
        self._tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self._tokenizer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tokenizer, name)

    def convert_ids_to_tokens(
        self, ids: list[int], skip_special_tokens: bool = False
    ) -> list[str | bytes]:
        if skip_special_tokens:
            return self._tokenizer.convert_ids_to_tokens(
                ids, skip_special_tokens=True
            )

        from mistral_common.tokens.tokenizers.base import SpecialTokenPolicy

        backend = self._tokenizer.tokenizer
        special_ids = self._tokenizer._special_token_ids_set
        return [
            backend.decode([token_id], SpecialTokenPolicy.KEEP)
            if token_id in special_ids
            else backend.id_to_byte_piece(token_id, SpecialTokenPolicy.KEEP)
            for token_id in ids
        ]


def _view_if_needed(tokenizer: Any, skip_special_tokens: bool) -> Any:
    if not skip_special_tokens and _is_affected_tokenizer(tokenizer):
        return _TekkenByteFallbackView(tokenizer)
    return tokenizer


def install() -> bool:
    """Install the process-local patch when explicitly enabled.

    Returns True only when this call installs the patch. Repeated calls are
    idempotent. No behavior changes when the opt-in environment flag is absent.
    """
    if not _enabled():
        return False

    import vllm.tokenizers.detokenizer_utils as utils
    import vllm.v1.engine.detokenizer as engine_detokenizer

    if getattr(utils, "_saber_mistral_utf8_patch", None) == PATCH_VERSION:
        return False

    original_prompt = utils.convert_prompt_ids_to_tokens
    original_incremental = utils.detokenize_incrementally

    @wraps(original_prompt)
    def convert_prompt_ids_to_tokens(
        tokenizer: Any,
        prompt_ids: list[int],
        skip_special_tokens: bool = False,
    ):
        return original_prompt(
            _view_if_needed(tokenizer, skip_special_tokens),
            prompt_ids,
            skip_special_tokens=skip_special_tokens,
        )

    @wraps(original_incremental)
    def detokenize_incrementally(
        tokenizer: Any,
        all_input_ids: list[int],
        prev_tokens: list[str] | None,
        prefix_offset: int,
        read_offset: int,
        skip_special_tokens: bool = False,
        spaces_between_special_tokens: bool = True,
    ):
        return original_incremental(
            _view_if_needed(tokenizer, skip_special_tokens),
            all_input_ids,
            prev_tokens,
            prefix_offset,
            read_offset,
            skip_special_tokens=skip_special_tokens,
            spaces_between_special_tokens=spaces_between_special_tokens,
        )

    # Patch both the defining module and the names imported by the engine.
    utils.convert_prompt_ids_to_tokens = convert_prompt_ids_to_tokens
    utils.detokenize_incrementally = detokenize_incrementally
    engine_detokenizer.convert_prompt_ids_to_tokens = convert_prompt_ids_to_tokens
    engine_detokenizer.detokenize_incrementally = detokenize_incrementally
    utils._saber_mistral_utf8_patch = PATCH_VERSION
    engine_detokenizer._saber_mistral_utf8_patch = PATCH_VERSION
    return True
