import logging
from contextlib import contextmanager
from time import perf_counter


LOGGER = logging.getLogger("etf_terminal.perf")


@contextmanager
def timed_block(label: str):
    """Log elapsed time for a dashboard workload block without changing UI behavior."""

    start = perf_counter()
    try:
        yield
    finally:
        LOGGER.info("%s took %.1fms", label, (perf_counter() - start) * 1000.0)
