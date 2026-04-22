# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger("jqktrader")
logger.setLevel(logging.DEBUG)
logger.propagate = False

fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(filename)s %(lineno)s: %(message)s"
)
ch = logging.StreamHandler()

ch.setFormatter(fmt)
logger.handlers.append(ch)
