import inspect
import logging
import os


def get_logger_by(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    try:
        from uvicorn.logging import DefaultFormatter

        formatter = DefaultFormatter(fmt="%(levelprefix)s %(name)s %(message)s")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except ImportError:
        logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    return logger


def get_logger() -> logging.Logger:
    stack = inspect.stack()
    caller_module = inspect.getmodule(stack[1][0]).__name__.split(".")[0]  # type: ignore[union-attr]
    return get_logger_by(caller_module)


logger = get_logger()
