from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Step:
    action: str
    selector: str | None = None
    value: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class TestCase:
    name: str
    steps: list[Step] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: ["generated"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tags": self.tags,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class UIElement:
    selector: str
    tag: str
    label: str = ""
    input_type: str = ""
    placeholder: str = ""
    text: str = ""
    options: tuple[str, ...] = ()
    click_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "selector": self.selector,
            "tag": self.tag,
            "label": self.label,
            "input_type": self.input_type,
            "placeholder": self.placeholder,
            "text": self.text,
            "options": list(self.options),
            "click_allowed": self.click_allowed,
        }


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    title: str
    elements: tuple[UIElement, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "elements": [element.to_dict() for element in self.elements],
        }
