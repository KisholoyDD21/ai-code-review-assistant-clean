from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_api_keys_are_not_requested_in_the_browser():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert not any("api key" in widget.label.lower() for widget in app.text_input)
    assert any("AI review unavailable" in item.value for item in app.warning)


def test_stale_results_are_cleared_when_review_inputs_change():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    app.session_state["review_result"] = "old result"
    app.session_state["review_fingerprint"] = "outdated"

    app.run()

    assert not app.exception
    assert app.session_state["review_result"] is None
    assert app.session_state["review_status"] == "stale"
    assert any("Previous results were cleared" in item.value for item in app.warning)


def test_old_error_is_cleared_when_inputs_change():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    app.session_state["review_status"] = "error"
    app.session_state["last_error"] = "Old input error"
    app.session_state["review_fingerprint"] = "outdated"

    app.run()

    assert not app.exception
    assert app.session_state["review_status"] == "idle"
    assert app.session_state["last_error"] is None


def test_privacy_and_terms_page_renders():
    page_path = Path(__file__).resolve().parents[1] / "pages" / "privacy_and_terms.py"
    app = AppTest.from_file(str(page_path)).run()

    assert not app.exception
    assert any("Privacy & Terms" in item.value for item in app.title)


def test_review_completes_with_static_analysis_when_ai_is_unavailable():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    app.text_area[0].set_value("def add(a, b):\n    return a + b\n")
    next(button for button in app.button if button.label == "Run review").click()

    app.run()

    assert not app.exception
    assert app.session_state["review_status"] == "static_only"
    assert any("Static analysis complete" in item.value for item in app.info)


def test_static_only_mode_needs_no_ai_provider_or_model():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    next(widget for widget in app.radio if widget.label == "Review mode").set_value(
        "Static analysis only"
    )
    app.run()

    assert not app.exception
    assert not app.selectbox
    assert not any("AI review unavailable" in item.value for item in app.warning)

    app.text_area[0].set_value("def add(a, b):\n    return a + b\n")
    next(button for button in app.button if button.label == "Run review").click()
    app.run()

    assert not app.exception
    assert app.session_state["review_status"] == "static_only"
    assert all(tab.label != "AI Review" for tab in app.tabs)
    assert any("No AI provider or model was used" in item.value for item in app.info)
