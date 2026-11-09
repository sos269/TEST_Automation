from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml


@dataclass(frozen=True)
class AIConfig:
    provider: str = "openai_compatible"
    model: str = "gpt-5.6-luna"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 60
    max_cases: int = 12
    allow_submit: bool = False


@dataclass(frozen=True)
class TargetConfig:
    start_url: str
    allowed_hosts: set[str]
    headless: bool = True
    timeout_ms: int = 10_000
    max_pages: int = 10
    max_actions_per_page: int = 12
    sample_data: dict[str, str] = field(default_factory=dict)
    ai: AIConfig = field(default_factory=AIConfig)

    @classmethod
    def from_file(cls, path: Path) -> "TargetConfig":
        content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        start_url = content["start_url"]
        parsed = urlparse(start_url)
        allowed_hosts = set(content.get("allowed_hosts") or [parsed.netloc])
        ai_content = content.get("ai") or {}
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("start_url 必须包含协议和主机名，例如 https://test.example.com")
        return cls(
            start_url=start_url,
            allowed_hosts=allowed_hosts,
            headless=bool(content.get("headless", True)),
            timeout_ms=int(content.get("timeout_ms", 10_000)),
            max_pages=int(content.get("max_pages", 10)),
            max_actions_per_page=int(content.get("max_actions_per_page", 12)),
            sample_data={str(key): str(value) for key, value in content.get("sample_data", {}).items()},
            ai=AIConfig(
                provider=str(ai_content.get("provider", "openai_compatible")),
                model=str(ai_content.get("model", "gpt-5.6-luna")),
                base_url=str(ai_content.get("base_url", "https://api.openai.com/v1")),
                api_key_env=str(ai_content.get("api_key_env", "OPENAI_API_KEY")),
                timeout_seconds=int(ai_content.get("timeout_seconds", 60)),
                max_cases=int(ai_content.get("max_cases", 12)),
                allow_submit=bool(ai_content.get("allow_submit", False)),
            ),
        )
