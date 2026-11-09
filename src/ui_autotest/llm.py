from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import AIConfig


class LLMClient(Protocol):
    def generate(self, instructions: str, user_input: str) -> str: ...


class _HTTPClient:
    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.api_key = os.environ.get(config.api_key_env, "")

    def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"模型 API 返回 HTTP {error.code}: {detail[:500]}") from error
        except URLError as error:
            raise RuntimeError(f"模型 API 网络请求失败: {error.reason}") from error

    def _require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(f"未设置模型 API Key 环境变量：{self.config.api_key_env}")
        return self.api_key


class OpenAICompatibleClient(_HTTPClient):
    """适配 OpenAI、DeepSeek、通义、智谱、vLLM、Ollama 等 Chat Completions 接口。"""

    def generate(self, instructions: str, user_input: str) -> str:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.config.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_input},
            ],
        }
        data = self._post(self.config.base_url.rstrip("/") + "/chat/completions", payload, headers)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("OpenAI 兼容 API 返回中缺少 choices.message.content") from error
        return _content_to_text(content)


class AnthropicClient(_HTTPClient):
    def generate(self, instructions: str, user_input: str) -> str:
        payload = {
            "model": self.config.model,
            "max_tokens": 4096,
            "system": instructions,
            "messages": [{"role": "user", "content": user_input}],
        }
        data = self._post(
            self.config.base_url.rstrip("/") + "/messages",
            payload,
            {"x-api-key": self._require_key(), "anthropic-version": "2023-06-01"},
        )
        try:
            return _content_to_text(data["content"])
        except (KeyError, TypeError) as error:
            raise RuntimeError("Anthropic API 返回中缺少 content") from error


class GeminiClient(_HTTPClient):
    def generate(self, instructions: str, user_input: str) -> str:
        key = self._require_key()
        endpoint = self.config.base_url.rstrip("/") + f"/models/{quote(self.config.model)}:generateContent?key={quote(key)}"
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": [{"text": user_input}]}],
            "generationConfig": {"temperature": 0.1},
        }
        data = self._post(endpoint, payload, {})
        try:
            return _content_to_text(data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini API 返回中缺少 candidates.content.parts") from error


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        if text_parts:
            return "".join(text_parts)
    raise RuntimeError("模型 API 返回了无法识别的文本格式")


def build_llm_client(config: AIConfig) -> LLMClient:
    provider = config.provider.lower().replace("-", "_")
    if provider in {"openai", "openai_compatible", "ollama", "vllm", "deepseek", "qwen", "zhipu"}:
        return OpenAICompatibleClient(config)
    if provider in {"anthropic", "claude"}:
        return AnthropicClient(config)
    if provider in {"gemini", "google"}:
        return GeminiClient(config)
    raise ValueError(f"不支持的 AI provider：{config.provider}")
