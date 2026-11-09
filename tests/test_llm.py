from ui_autotest.config import AIConfig
from ui_autotest.llm import AnthropicClient, GeminiClient, OpenAICompatibleClient, build_llm_client


def test_build_llm_client_supports_multiple_providers() -> None:
    assert isinstance(build_llm_client(AIConfig(provider="openai")), OpenAICompatibleClient)
    assert isinstance(build_llm_client(AIConfig(provider="ollama")), OpenAICompatibleClient)
    assert isinstance(build_llm_client(AIConfig(provider="anthropic")), AnthropicClient)
    assert isinstance(build_llm_client(AIConfig(provider="gemini")), GeminiClient)


def test_openai_compatible_client_does_not_require_key_for_local_models() -> None:
    client = OpenAICompatibleClient(
        AIConfig(provider="ollama", base_url="http://localhost:11434/v1", api_key_env="MISSING_API_KEY")
    )

    assert client.api_key == ""
