import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("-m", default=""):
        return
    skip_live = pytest.mark.skip(reason="needs Kindle running; use `pytest -m live`")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
