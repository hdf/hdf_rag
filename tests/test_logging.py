import logging

from app.logging_config import application_logging


def test_file_logging_appends_without_duplicate_handlers(tmp_path):
    path = tmp_path / "logs" / "app.log"
    logger = logging.getLogger("app.test")
    for message in ("First startup", "Second startup"):
        with application_logging(str(path)):
            logger.info(message)
    text = path.read_text(encoding="utf-8")
    assert text.count("First startup") == 1
    assert text.count("Second startup") == 1
    assert "INFO app.test" in text


def test_file_rotation_preserves_previous_records(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("x" * (5 * 1024 * 1024), encoding="utf-8")
    with application_logging(str(path)):
        logging.getLogger("app.test").warning("New record")
    assert (tmp_path / "app.log.1").stat().st_size == 5 * 1024 * 1024
    assert "New record" in path.read_text(encoding="utf-8")
