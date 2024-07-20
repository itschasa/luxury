import logging
import datetime
from colorama import Fore



stdout_log_level = logging.DEBUG
file_log_level = logging.DEBUG
ws_log_level = logging.DEBUG
file_log_name = 'logs/{:%Y-%m-%d %H.%M.%S}.log'.format(datetime.datetime.now())
log_format = '[%(asctime)s] [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)'


class ColourFormatter(logging.Formatter):
    grey = Fore.LIGHTBLACK_EX
    yellow = Fore.YELLOW
    red = Fore.LIGHTRED_EX
    bold_red = Fore.RED
    blue = Fore.LIGHTBLUE_EX
    reset = Fore.RESET
    format = log_format

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


class WSHandler(logging.Handler):
    def emit(self, record): 
        log_entry = self.format(record)
        
        from web.app import admin_sockets

        sock_to_remove = []

        for sock in admin_sockets:
            try:
                sock.send(log_entry)
            except:
                sock_to_remove.append(sock)
        
        for sock in sock_to_remove:
            try:
                admin_sockets.remove(sock)
            except:
                pass


logger = logging.getLogger("backend")
logger.setLevel(logging.DEBUG)

ws_handler = WSHandler()
ws_handler.setLevel(ws_log_level)
ws_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(ws_handler)

std_handler = logging.StreamHandler()
std_handler.setLevel(stdout_log_level)
std_handler.setFormatter(ColourFormatter())
logger.addHandler(std_handler)

file_handler = logging.FileHandler(file_log_name)
file_handler.setLevel(file_log_level)
file_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(file_handler)
