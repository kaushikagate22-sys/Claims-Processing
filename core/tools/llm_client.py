"""
core.tools.llm_client
====================
A thin, swappable, **multi-provider** LLM wrapper.

Providers (auto-detected, no code change to switch):
  * openai     — when OPENAI_API_KEY is set (uses native JSON mode for extraction)
  * anthropic  — when ANTHROPIC_API_KEY is set
  * offline    — deterministic fallback so the whole pipeline runs with NO key

Selection order:
  1. explicit env LLM_PROVIDER = openai | anthropic | offline
  2. else whichever API key is present (OpenAI preferred if both)
  3. else offline

Every agent/tool uses only two primitives, so the provider is invisible to them:
  * complete(prompt, system)      -> free text
  * extract_json(prompt, schema)  -> structured dict
"""
from __future__ import annotations

import json
import os
import base64
import re
from typing import Any, Dict, Optional

from core.utils.logger import get_logger

log = get_logger("llm")

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-6",
}


def resolve_provider(
    explicit: Optional[str],
    openai_key: Optional[str],
    anthropic_key: Optional[str],
) -> str:
    """Pure function (easy to unit-test) that decides which provider to use."""
    if explicit:
        return explicit.strip().lower()
    if openai_key:
        return "openai"
    if anthropic_key:
        return "anthropic"
    return "offline"



def _encode_image(img) -> Optional[tuple]:
    """Return (media_type, base64) for a file path or raw bytes; None on failure."""
    try:
        if isinstance(img, (bytes, bytearray)):
            data = bytes(img); ext = ""
        else:
            from pathlib import Path as _P
            p = _P(str(img))
            if not p.exists():
                return None
            data = p.read_bytes(); ext = p.suffix.lower()
        media = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif",
        }.get(ext, "image/jpeg")
        return media, base64.b64encode(data).decode("ascii")
    except Exception:
        return None


class LLMClient:
    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        openai_key = os.getenv("OPENAI_API_KEY") if provider != "anthropic" else None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY") if provider != "openai" else None
        if api_key and provider == "openai":
            openai_key = api_key
        if api_key and provider == "anthropic":
            anthropic_key = api_key

        chosen = resolve_provider(provider or os.getenv("LLM_PROVIDER"), openai_key, anthropic_key)
        self.model = (
            model
            or os.getenv("LLM_MODEL")
            or os.getenv(f"{chosen.upper()}_MODEL")
            or _DEFAULT_MODELS.get(chosen)
        )
        self._client = None
        self.mode = "offline"

        if chosen == "openai" and openai_key:
            self._init_openai(openai_key)
        elif chosen == "anthropic" and anthropic_key:
            self._init_anthropic(anthropic_key)

        log.info("LLMClient mode=%s model=%s", self.mode, self.model)

    # --- provider init ----------------------------------------------------
    def _init_openai(self, key: str) -> None:
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=key)
            self.mode = "openai"
        except Exception as exc:  # noqa: BLE001
            log.warning("openai unavailable (%s); using offline fallback", exc)

    def _init_anthropic(self, key: str) -> None:
        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=key)
            self.mode = "anthropic"
        except Exception as exc:  # noqa: BLE001
            log.warning("anthropic unavailable (%s); using offline fallback", exc)

    # --- public API -------------------------------------------------------
    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        if self.mode == "openai":
            return self._complete_openai(prompt, system, max_tokens)
        if self.mode == "anthropic":
            return self._complete_anthropic(prompt, system, max_tokens)
        return self._fallback_complete(prompt, system)

    def extract_json(
        self, prompt: str, schema: Dict[str, str], system: str = ""
    ) -> Dict[str, Any]:
        sys = (
            (system or "You are a precise information-extraction engine.")
            + " Respond with ONLY a single JSON object, no prose, no code fences."
        )
        field_lines = "\n".join(f'  "{k}": {v}' for k, v in schema.items())
        full = f"{prompt}\n\nReturn JSON with exactly these fields:\n{{\n{field_lines}\n}}"

        if self.mode == "openai":
            raw = self._complete_openai(full, sys, 1024, json_mode=True)
        elif self.mode == "anthropic":
            raw = self._complete_anthropic(full, sys, 1024)
        else:
            raw = self._fallback_complete(full, sys)
        return _safe_json(raw, schema)

    @property
    def vision_available(self) -> bool:
        """True when the active provider can analyse images."""
        return self.mode in ("openai", "anthropic")

    def analyze_images(
        self, prompt: str, images: list, system: str = "", json_mode: bool = True, max_tokens: int = 800
    ) -> str:
        """Multimodal: send a prompt plus one or more images, return the model's text.
        `images` is a list of file paths or raw bytes. Returns "" if vision is offline."""
        encoded = [_encode_image(img) for img in (images or [])]
        encoded = [e for e in encoded if e]
        if not encoded:
            return ""
        if self.mode == "openai":
            content = [{"type": "text", "text": prompt}]
            for media, b64 in encoded:
                content.append({"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}})
            kwargs: Dict[str, Any] = {
                "model": self.model, "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system or "You are a meticulous visual claims inspector."},
                    {"role": "user", "content": content},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        if self.mode == "anthropic":
            content = [{"type": "text", "text": prompt}]
            for media, b64 in encoded:
                content.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}})
            msg = self._client.messages.create(
                model=self.model, max_tokens=max_tokens,
                system=system or "You are a meticulous visual claims inspector.",
                messages=[{"role": "user", "content": content}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return ""  # offline

    # --- openai -----------------------------------------------------------
    def _complete_openai(
        self, prompt: str, system: str, max_tokens: int, json_mode: bool = False
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    # --- anthropic --------------------------------------------------------
    def _complete_anthropic(self, prompt: str, system: str, max_tokens: int) -> str:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )

    # --- offline fallback -------------------------------------------------
    def _fallback_complete(self, prompt: str, system: str) -> str:
        if "Return JSON with exactly these fields" in prompt:
            return self._fallback_extract(prompt)
        return "[offline-llm] No LLM API key set — returning heuristic output."

    @staticmethod
    def _fallback_extract(prompt: str) -> str:
        fields = re.findall(r'"([^"]+)":', prompt.split("Return JSON")[-1])
        source = prompt.split("Return JSON")[0]
        found: Dict[str, Any] = {}
        kv = dict(re.findall(r"(?m)^\s*([A-Za-z _/]+?)\s*[:=]\s*(.+?)\s*$", source))
        norm = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in kv.items()}
        for f in fields:
            key = f.lower()
            val = norm.get(key)
            if val is None:
                for nk, nv in norm.items():
                    if key in nk or nk in key:
                        val = nv
                        break
            found[f] = val
        return json.dumps(found)


def _safe_json(raw: str, schema: Dict[str, str]) -> Dict[str, Any]:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return {k: data.get(k) for k in schema}
        except json.JSONDecodeError:
            pass
    return {k: None for k in schema}
