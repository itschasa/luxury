import base64
import random
import json
import time
import hashlib
from flask import request, jsonify
from functools import wraps

from utils import log_setup



log = log_setup.logger


def rand_str_full(length=32):
    return ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') for _ in range(length))


def rand_str_hex(length=64):
    return ''.join(random.choice('abcdef1234567890') for _ in range(length))


def jd(data):
    return json.dumps(data, separators=(',', ':'))


def jl(data):
    return json.loads(data)


def typ(data, type):
    """Raises `KeyError` when `isinstance(data, type) == False`.
    
    Otherwise, returns `data`."""

    if type == int:
        try: data = int(data)
        except: pass

    if not isinstance(data, type):
        raise KeyError
    return data


def ms():
    "Current time in milliseconds."
    return int(time.time() * 1000)


def sha256(data: str) -> str:
    """Returns the SHA-256 hash of the given data as a hexadecimal string."""
    hash_object = hashlib.sha256(data.encode())
    return hash_object.hexdigest()


def force_json(cls):
    @wraps(cls)
    def wrapper(*args, **kwargs):
        if not request.get_json(force=True, silent=True):
            return jsonify({'error': True, 'message': 'Malformed or missing JSON body.'}), 400
        return cls(*args, **kwargs)
    return wrapper


def validate_string(string: str, type: str, minlength: int = None, maxlength: int = None, setlength=None):
    "types: username, email, rand_chars"
    if string is None:
        return None
    
    if type == "username":
        if string.lower() == 'system' or string.lower() == 'anonymous':
            return None
        
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm_.-"
    elif type == "email":
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm@-_."
        if "@" not in string or "." not in string:
            return False
        
    elif type == "rand_chars":
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm"
    else:
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm_.:;\"@-<=>?!()}[]{#£$%^&*^',/\\|~` "
    
    if not setlength:
        if minlength:
            if len(string) < minlength:
                return False
        
        if maxlength:
            if len(string) > maxlength:
                return False
    else:
        if len(string) != setlength:
            return False
        
    for char in string.lower():
        if char not in chars:
            return None
    
    return string


def get_discord_id(token: str):
    return int(base64.b64decode(token.split(".")[0] + "=======").decode())


from utils import mail, snowflake, hasher, turnstile
from utils.turnstile import Captcha
