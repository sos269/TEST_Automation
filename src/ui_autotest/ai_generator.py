from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from .config import TargetConfig
from .models import PageSnapshot, Step, TestCase
from .llm import LLMClient, build_llm_client
from .snapshot import PageSnapshotCollector

_SUPPORTED_ACTIONS = {"navigate", "fill", "expect_visible", "expect_value", "select_option", "click"}


class AICaseGenerator:
    """将页面元数据交给模型规划，再严格校验为可执行的安全用例。"""

    def __init__(self, config: TargetConfig, client: LLMClient | None = None) -> None:
        self.config = config
        self.client = client

    def generate(self) -> list[TestCase]:
        snapshots = PageSnapshotCollector(self.config).collect()
        return self.generate_from_snapshots(snapshots)

    def generate_from_snapshots(self, snapshots: list[PageSnapshot]) -> list[TestCase]:
        if not snapshots:
            return []
        response = self._client().generate(
            instructions=self._instructions(),
            user_input=json.dumps({"pages": [snapshot.to_dict() for snapshot in snapshots]}, ensure_ascii=False),
        )
        return self._validate_cases(self._parse_output(response), snapshots)

    def _client(self) -> LLMClient:
        if self.client is not None:
            return self.client
        return build_llm_client(self.config.ai)

    def _instructions(self) -> str:
        submit_rule = "仅当 click_allowed 为 true 时才可点击提交动作。" if self.config.ai.allow_submit else "不能点击提交动作。"
        return f"""你是 Web UI 测试设计师。仅根据输入的 pages 元数据生成最多 {self.config.ai.max_cases} 条非破坏性 UI 自动化用例。
返回严格 JSON：{{\"cases\":[{{\"name\":\"...\",\"tags\":[\"ai-generated\"],\"steps\":[{{\"action\":\"...\",\"selector\":\"...\",\"value\":\"...\"}}]}}]}}，不要使用 Markdown。
每条用例以 navigate 开始。只可使用输入中出现的 URL 和 selector。只可使用 navigate、fill、expect_visible、expect_value、select_option、click。
fill 使用测试样例值，不要臆造账号或密码。click 仅可用于 click_allowed 为 true 的元素，且不能点击删除、支付或其他有副作用的动作。{submit_rule}
优先覆盖页面可访问性、关键输入校验、可见性以及安全导航。"""

    @staticmethod
    def _parse_output(text: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("AI 未返回有效 JSON，用例未写入文件。") from error
        cases = data.get("cases")
        if not isinstance(cases, list):
            raise ValueError("AI 输出中缺少 cases 数组。")
        return cases

    def _validate_cases(self, raw_cases: list[dict[str, Any]], snapshots: list[PageSnapshot]) -> list[TestCase]:
        pages = {snapshot.url: snapshot for snapshot in snapshots}
        accepted: list[TestCase] = []
        for raw_case in raw_cases[: self.config.ai.max_cases]:
            try:
                accepted.append(self._validate_case(raw_case, pages))
            except (KeyError, TypeError, ValueError) as error:
                print(f"跳过 AI 用例：{error}")
        return accepted

    def _validate_case(self, raw_case: dict[str, Any], pages: dict[str, PageSnapshot]) -> TestCase:
        name = raw_case["name"]
        steps = raw_case["steps"]
        if not isinstance(name, str) or not name.strip() or not isinstance(steps, list) or not steps:
            raise ValueError("用例名称或步骤无效")
        current_page: PageSnapshot | None = None
        parsed_steps: list[Step] = []
        for raw_step in steps:
            action = raw_step["action"]
            if action not in _SUPPORTED_ACTIONS:
                raise ValueError(f"不支持的动作：{action}")
            if action == "navigate":
                url = raw_step["value"]
                if url not in pages or urlparse(url).netloc not in self.config.allowed_hosts:
                    raise ValueError(f"未采集的页面：{url}")
                current_page = pages[url]
                parsed_steps.append(Step(action=action, value=url))
                continue
            if current_page is None:
                raise ValueError("首个步骤必须为 navigate")
            selector = raw_step["selector"]
            element = next((item for item in current_page.elements if item.selector == selector), None)
            if element is None:
                raise ValueError(f"未采集的选择器：{selector}")
            value = raw_step.get("value")
            if action in {"fill", "expect_value", "select_option"} and not isinstance(value, str):
                raise ValueError(f"动作 {action} 缺少 value")
            if action == "click" and not element.click_allowed:
                raise ValueError(f"不允许点击：{selector}")
            if action == "select_option" and value not in element.options:
                raise ValueError(f"下拉值不在页面选项中：{value}")
            parsed_steps.append(Step(action=action, selector=selector, value=value if isinstance(value, str) else None))
        if parsed_steps[0].action != "navigate":
            raise ValueError("首个步骤必须为 navigate")
        tags = raw_case.get("tags", [])
        safe_tags = [tag for tag in tags if isinstance(tag, str)][:5] if isinstance(tags, list) else []
        return TestCase(name=name.strip(), tags=["ai-generated", *safe_tags], steps=parsed_steps)
