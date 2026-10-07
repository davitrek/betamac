import json
import logging

from betamac import configure_file_logger, create_app


def test_configure_file_logger(tmp_path):
    log_path = tmp_path / "logs" / "test.jsonl"
    logger = logging.getLogger("betamac.test_logging")

    try:
        # second call must not add a second handler
        configure_file_logger(logger.name, log_path, 1024, 1)
        configure_file_logger(logger.name, log_path, 1024, 1)
        assert len(logger.handlers) == 1

        logger.info(json.dumps({"text": "héllo 👋"}, ensure_ascii=False))
        logger.handlers[0].flush()

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line) for line in lines] == [{"text": "héllo 👋"}]
    finally:
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()


def test_create_app_testing_adds_no_file_handlers(tmp_path):
    create_app({"TESTING": True, "LOG_DIR": tmp_path / "logs"})

    assert not (tmp_path / "logs").exists()
