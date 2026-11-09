from __future__ import annotations

from pathlib import Path

import yaml
from playwright.sync_api import Page, expect, sync_playwright

from .config import TargetConfig


class CaseRunner:
    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    def run(self, case_file: Path) -> tuple[int, int]:
        document = yaml.safe_load(case_file.read_text(encoding="utf-8")) or {}
        cases = document.get("cases", [])
        passed = 0
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            try:
                for case in cases:
                    page = browser.new_page()
                    page.set_default_timeout(self.config.timeout_ms)
                    try:
                        for step in case["steps"]:
                            self._run_step(page, step)
                        passed += 1
                        print(f"PASS {case['name']}")
                    except Exception as error:
                        print(f"FAIL {case['name']}: {error}")
                    finally:
                        page.close()
            finally:
                browser.close()
        return passed, len(cases)

    @staticmethod
    def _run_step(page: Page, step: dict[str, str]) -> None:
        action = step["action"]
        if action == "navigate":
            page.goto(step["value"], wait_until="domcontentloaded")
        elif action == "expect_title":
            expect(page).not_to_have_title("")
        elif action == "fill":
            page.locator(step["selector"]).fill(step["value"])
        elif action == "expect_value":
            expect(page.locator(step["selector"])).to_have_value(step["value"])
        elif action == "expect_visible":
            expect(page.locator(step["selector"])).to_be_visible()
        elif action == "click":
            page.locator(step["selector"]).click()
        elif action == "select_option":
            page.locator(step["selector"]).select_option(step["value"])
        elif action == "select_first":
            page.locator(step["selector"]).select_option(index=0)
        else:
            raise ValueError(f"未知步骤动作：{action}")
