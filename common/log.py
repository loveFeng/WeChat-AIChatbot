import logging
import sys
from logging.handlers import TimedRotatingFileHandler


def reset_logger(log, name='wechat'):
    for handler in log.handlers:
        handler.close()
        log.removeHandler(handler)
        del handler
    log.handlers.clear()
    log.propagate = False
    console_handle = logging.StreamHandler(sys.stdout)
    console_handle.setFormatter(
        logging.Formatter(
            "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # file_handle = logging.FileHandler("run.log", encoding="utf-8")
    log_file = name
    # file_handle = TimedRotatingFileHandler(log_file, when="midnight", encoding='utf-8')
    file_handle = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=0, encoding='utf-8')
    file_handle.suffix = "%Y-%m-%d.log"
    file_handle.setFormatter(
        logging.Formatter(
            "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(file_handle)
    log.addHandler(console_handle)


def _get_logger():
    log = logging.getLogger("log")
    reset_logger(log)
    log.setLevel(logging.DEBUG)
    return log


# 日志句柄
logger = _get_logger()

