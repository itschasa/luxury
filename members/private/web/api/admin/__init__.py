from typing import Union
from functools import wraps
from flask import jsonify

from config import config
from web.api.auth import AuthPayload, APIKeyPayload



def require_admin(cls):
    @wraps(cls)
    def wrapper(key_payload: Union[AuthPayload, APIKeyPayload], *args, **kwargs):
        if key_payload.user_id not in config().admins:
            return jsonify({'error': True, 'message': 'Unauthorized.'}), 401
        
        if isinstance(key_payload, APIKeyPayload):
            return jsonify({'error': True, 'message': 'API keys are not authorized at admin endpoints.'}), 401

        return cls(key_payload, *args, **kwargs)
    return wrapper

from web.api.admin import chat, logs, tokens, user
