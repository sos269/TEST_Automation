from pathlib import Path

from ui_autotest.config import TargetConfig


def test_config_defaults_allowed_host(tmp_path: Path) -> None:
    config_file = tmp_path / "target.yaml"
    config_file.write_text("start_url: https://test.example.com/login\n", encoding="utf-8")

    config = TargetConfig.from_file(config_file)

    assert config.allowed_hosts == {"test.example.com"}
