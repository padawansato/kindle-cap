from unittest.mock import MagicMock, patch

from kindle_cap.config import Direction
from kindle_cap.keys import send_next_page


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_rtl_sends_right_arrow(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "key code 124" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_ltr_sends_left_arrow(mock_run: MagicMock) -> None:
    send_next_page(Direction.LTR)
    cmd = mock_run.call_args[0][0]
    assert "key code 123" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_targets_kindle_process(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    cmd = mock_run.call_args[0][0]
    assert "Kindle" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_uses_check_true(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    assert mock_run.call_args.kwargs.get("check") is True
