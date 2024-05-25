import logging

from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx

logger = logging.getLogger("gas_station_app")


def get_remote_ip() -> str | None:
    """Get remote ip."""

    try:
        ctx = get_script_run_ctx()
        if ctx is None:
            return None

        session_info = runtime.get_instance().get_client(ctx.session_id)

        if session_info is None:
            return None
        else:
            forwarded_ip = session_info.request.headers.get("X-FORWARDED-FOR")
            if forwarded_ip is not None:
                # split to get the last ip
                return forwarded_ip.split(",")[-1].strip()

    except Exception as e:
        logger.error("Error getting remote ip")
        return None


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.user_ip = get_remote_ip()
        return super().filter(record)


def init_logging():
    # Make sure to instanciate the logger only once
    # otherwise, it will create a StreamHandler at every run
    # and duplicate the messages

    # create a custom logger
    logger = logging.getLogger("gas_station_app")
    if logger.handlers:  # logger is already setup, don't setup again
        return
    logger.propagate = False
    logger.setLevel(logging.INFO)
    # in the formatter, use the variable "user_ip"
    formatter = logging.Formatter(
        "%(name)s %(asctime)s %(levelname)s [user_ip=%(user_ip)s] - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.addFilter(ContextFilter())
    handler.setFormatter(formatter)
    logger.addHandler(handler)
