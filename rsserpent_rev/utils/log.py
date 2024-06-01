import logging
import os

logger = logging.getLogger("rsserpent")
try:
    from uvicorn.logging import DefaultFormatter

    formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
except ImportError:
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
