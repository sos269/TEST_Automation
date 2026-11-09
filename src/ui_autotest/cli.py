from __future__ import annotations

import argparse
from pathlib import Path

from .config import TargetConfig
from .ai_generator import AICaseGenerator
from .generator import CaseGenerator, write_cases
from .runner import CaseRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playwright Web UI 自动化用例生成与执行")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "execute"):
        child = subparsers.add_parser(command)
        child.add_argument("--config", type=Path, required=True, help="目标配置 YAML")
        child.add_argument("--cases", type=Path, default=Path("tests/generated_cases.yaml"), help="用例 YAML")
        if command == "generate":
            child.add_argument("--ai", action="store_true", help="使用 AI 根据页面结构生成用例（需要 OPENAI_API_KEY）")
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    config = TargetConfig.from_file(arguments.config)
    if arguments.command == "generate":
        cases = AICaseGenerator(config).generate() if arguments.ai else CaseGenerator(config).generate()
        write_cases(cases, arguments.cases)
        print(f"已生成 {len(cases)} 条用例：{arguments.cases}")
        return
    passed, total = CaseRunner(config).run(arguments.cases)
    print(f"执行完成：{passed}/{total} 通过")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
