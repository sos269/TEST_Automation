from __future__ import annotations

from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.sync_api import Browser, Page, sync_playwright

from .config import TargetConfig
from .models import PageSnapshot, UIElement

_DANGEROUS_TERMS = ("delete", "remove", "destroy", "pay", "购买", "删除", "移除", "支付")
_SUBMIT_TERMS = ("submit", "提交")


class PageSnapshotCollector:
    """采集用于 AI 规划的最小页面元数据，不读取页面正文或输入值。"""

    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    def collect(self) -> list[PageSnapshot]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            try:
                return self._crawl(browser)
            finally:
                browser.close()

    def _crawl(self, browser: Browser) -> list[PageSnapshot]:
        page = browser.new_page()
        page.set_default_timeout(self.config.timeout_ms)
        queue = deque([self.config.start_url])
        visited: set[str] = set()
        snapshots: list[PageSnapshot] = []
        while queue and len(visited) < self.config.max_pages:
            url = urldefrag(queue.popleft())[0]
            if url in visited or not self._is_allowed(url):
                continue
            visited.add(url)
            try:
                page.goto(url, wait_until="domcontentloaded")
                snapshots.append(self._snapshot_page(page, url))
                queue.extend(self._links(page, url, visited))
            except Exception as error:
                print(f"扫描失败 {url}: {error}")
        page.close()
        return snapshots

    def _snapshot_page(self, page: Page, url: str) -> PageSnapshot:
        elements: list[UIElement] = []
        locator = page.locator("a[href], button, input, textarea, select, [role=button]")
        for index in range(min(locator.count(), self.config.max_actions_per_page)):
            element = locator.nth(index)
            try:
                elements.append(self._element_snapshot(element, index))
            except Exception as error:
                print(f"跳过无法解析的控件: {error}")
        return PageSnapshot(url=url, title=page.title() or url, elements=tuple(elements))

    def _element_snapshot(self, element, index: int) -> UIElement:
        tag = element.evaluate("node => node.tagName.toLowerCase()")
        input_type = (element.get_attribute("type") or "").lower()
        label = element.get_attribute("aria-label") or element.get_attribute("name") or ""
        text = (element.inner_text() or "").strip()[:120]
        selector = self._selector_for(element, index)
        options = ()
        if tag == "select":
            options = tuple(element.locator("option").evaluate_all("items => items.map(item => item.value).filter(Boolean)"))
        click_label = f"{label} {text}".lower()
        is_submit = input_type == "submit" or any(term in click_label for term in _SUBMIT_TERMS)
        click_allowed = (
            tag in {"a", "button"}
            and (self.config.ai.allow_submit or not is_submit)
            and not any(term in click_label for term in _DANGEROUS_TERMS)
        )
        return UIElement(
            selector=selector,
            tag=tag,
            label=label[:120],
            input_type=input_type,
            placeholder=(element.get_attribute("placeholder") or "")[:120],
            text=text,
            options=options,
            click_allowed=click_allowed,
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
        return f"a[href], button, input, textarea, select, [role=button] >> nth={index}"

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
