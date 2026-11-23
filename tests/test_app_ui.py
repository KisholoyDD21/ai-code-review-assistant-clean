from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_api_keys_are_not_requested_in_the_browser():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert not any("api key" in widget.label.lower() for widget in app.text_input)
