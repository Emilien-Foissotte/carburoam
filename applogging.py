import logging


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
        "%(name)s %(asctime)s %(levelname)s - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
