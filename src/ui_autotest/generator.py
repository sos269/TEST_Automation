from __future__ import annotations

from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import yaml
from playwright.sync_api import Browser, Page, sync_playwright

from .config import TargetConfig
from .models import Step, TestCase


class CaseGenerator:
    """以非破坏性动作为主扫描页面，并将发现的交互点生成 YAML 用例。"""

    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    def generate(self) -> list[TestCase]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            try:
                return self._crawl(browser)
            finally:
                browser.close()

    def _crawl(self, browser: Browser) -> list[TestCase]:
        page = browser.new_page()
        page.set_default_timeout(self.config.timeout_ms)
        queue = deque([self.config.start_url])
        visited: set[str] = set()
        cases: list[TestCase] = []

        while queue and len(visited) < self.config.max_pages:
            url = urldefrag(queue.popleft())[0]
            if url in visited or not self._is_allowed(url):
                continue
            visited.add(url)
            try:
                page.goto(url, wait_until="domcontentloaded")
                cases.extend(self._page_cases(page, url))
                queue.extend(self._links(page, url, visited))
            except Exception as error:  # 单页不可用不应中断其他页面扫描
                cases.append(
                    TestCase(
                        name=f"页面可访问性：{url}",
                        tags=["generated", "scan-error"],
                        steps=[Step(action="navigate", value=url), Step(action="expect_title")],
                    )
                )
                print(f"扫描失败 {url}: {error}")
        return cases

    def _page_cases(self, page: Page, url: str) -> list[TestCase]:
        title = page.title() or url
        cases = [
            TestCase(
                name=f"页面可访问性：{title}",
                steps=[Step(action="navigate", value=url), Step(action="expect_title")],
            )
        ]
        interactive = page.locator("button, input, textarea, select, [role=button]")
        for index in range(min(interactive.count(), self.config.max_actions_per_page)):
            element = interactive.nth(index)
            try:
                selector = self._selector_for(element, index)
                tag_name = element.evaluate("node => node.tagName.toLowerCase()")
                input_type = (element.get_attribute("type") or "").lower()
                label = element.get_attribute("aria-label") or element.get_attribute("name") or selector
                if tag_name in {"input", "textarea"} and input_type not in {"checkbox", "radio", "submit", "button", "file", "hidden"}:
                    cases.append(self._fill_case(url, label, selector, input_type))
                elif tag_name == "select":
                    cases.append(
                        TestCase(
                            name=f"选择控件可操作：{label}",
                            steps=[Step(action="navigate", value=url), Step(action="select_first", selector=selector)],
                        )
                    )
            except Exception as error:
                print(f"跳过无法解析的控件: {error}")
        return cases

    def _fill_case(self, url: str, label: str, selector: str, input_type: str) -> TestCase:
        value_key = "email" if input_type == "email" else "password" if input_type == "password" else "text"
        return TestCase(
            name=f"输入控件可编辑：{label}",
            steps=[
                Step(action="navigate", value=url),
                Step(action="fill", selector=selector, value=self.config.sample_data.get(value_key, "自动化测试")),
                Step(action="expect_value", selector=selector, value=self.config.sample_data.get(value_key, "自动化测试")),
            ],
        )

    @staticmethod
    def _selector_for(element, index: int) -> str:
        test_id = element.get_attribute("data-testid")
        if test_id:
            return f'[data-testid="{test_id}"]'
        element_id = element.get_attribute("id")
        if element_id:
            return f"#{element_id}"
        name = element.get_attribute("name")
        if name:
            return f'[name="{name}"]'
        return f"button, input, textarea, select, [role=button] >> nth={index}"

    def _links(self, page: Page, base_url: str, visited: set[str]) -> list[str]:
        hrefs = page.locator("a[href]").evaluate_all("links => links.map(link => link.getAttribute('href'))")
        return [
            resolved
            for href in hrefs
            if href and (resolved := urldefrag(urljoin(base_url, href))[0]) not in visited and self._is_allowed(resolved)
        ]

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and parsed.netloc in self.config.allowed_hosts


def write_cases(cases: list[TestCase], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump({"cases": [case.to_dict() for case in cases]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
