import logging
import os

from uvicorn.logging import DefaultFormatter

logger = logging.getLogger("rsserpent")
formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
