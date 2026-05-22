from forge.main import app


def test_app_title() -> None:
    assert app.title == "Forge API"
