import logging
from contextvars import ContextVar
import colorlog


request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str:
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class SuppressAFCFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg and isinstance(record.msg, str) and "AFC is enabled" in record.msg:
            return False
        return True


def configure_logging() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-7s%(reset)s | %(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SuppressAFCFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False
