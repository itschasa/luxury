import logging
import datetime
from colorama import Fore

stdout_log_level = logging.DEBUG
file_log_level = logging.DEBUG
file_log_name = 'logs/{:%Y-%m-%d %H.%M.%S}.log'.format(datetime.datetime.now())

class CustomFormatter(logging.Formatter):
    grey = Fore.LIGHTBLACK_EX
    yellow = Fore.YELLOW
    red = Fore.LIGHTRED_EX
    bold_red = Fore.RED
    blue = Fore.LIGHTBLUE_EX
    reset = Fore.RESET
    format = "[%(asctime)s] [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: blue + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
      
logger = logging.getLogger("backend")
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(stdout_log_level)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

file_handler = logging.FileHandler(file_log_name)
file_handler.setLevel(file_log_level)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s (%(filename)s:%(lineno)d)'))
logger.addHandler(file_handler)