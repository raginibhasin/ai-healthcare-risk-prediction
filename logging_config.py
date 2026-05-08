<<<<<<< HEAD
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    if not os.path.exists('logs'):
        os.mkdir('logs')

    handler = RotatingFileHandler('logs/security.log', maxBytes=10000, backupCount=3)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))

    logger = logging.getLogger('security')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger

=======
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    if not os.path.exists('logs'):
        os.mkdir('logs')

    handler = RotatingFileHandler('logs/security.log', maxBytes=10000, backupCount=3)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))

    logger = logging.getLogger('security')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger

>>>>>>> cb9d55459c2b5641af4c1264e6857fd8344774fc
security_logger = setup_logging()