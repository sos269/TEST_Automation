from ui_autotest.ai_generator import AICaseGenerator
from ui_autotest.config import TargetConfig
from ui_autotest.models import PageSnapshot, UIElement


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.output_text


def test_ai_case_generation_parses_model_response() -> None:
    config = TargetConfig(start_url="https://test.example.com", allowed_hosts={"test.example.com"})
    snapshot = PageSnapshot(
        url="https://test.example.com",
        title="Example",
        elements=(UIElement(selector="#email", tag="input", input_type="email"),),
    )
    client = FakeClient(
        '{"cases":[{"name":"邮箱校验","steps":[{"action":"navigate","value":"https://test.example.com"},'
        '{"action":"expect_visible","selector":"#email"}]}]}'
    )

    cases = AICaseGenerator(config, client=client).generate_from_snapshots([snapshot])

    assert cases[0].name == "邮箱校验"
    assert client.calls[0]["instructions"]


def test_ai_case_validation_accepts_collected_metadata_only() -> None:
    config = TargetConfig(start_url="https://test.example.com", allowed_hosts={"test.example.com"})
    snapshot = PageSnapshot(
        url="https://test.example.com",
        title="Example",
        elements=(UIElement(selector="#email", tag="input", input_type="email"),),
    )

    cases = AICaseGenerator(config)._validate_cases(
        [
            {
                "name": "邮箱可以输入",
                "steps": [
                    {"action": "navigate", "value": "https://test.example.com"},
                    {"action": "fill", "selector": "#email", "value": "tester@example.com"},
                    {"action": "expect_value", "selector": "#email", "value": "tester@example.com"},
                ],
            }
        ],
        [snapshot],
    )

    assert cases[0].tags == ["ai-generated"]
    assert len(cases[0].steps) == 3


def test_ai_case_validation_rejects_unknown_selector() -> None:
    config = TargetConfig(start_url="https://test.example.com", allowed_hosts={"test.example.com"})
    snapshot = PageSnapshot(url="https://test.example.com", title="Example", elements=())

    cases = AICaseGenerator(config)._validate_cases(
        [
            {
                "name": "无效用例",
                "steps": [
                    {"action": "navigate", "value": "https://test.example.com"},
                    {"action": "expect_visible", "selector": "#not-found"},
                ],
            }
        ],
        [snapshot],
    )

    assert cases == []
