import jwt
from dataclasses import dataclass
import dataclasses
import dacite
from typing import Union
from functools import wraps
from flask import request, jsonify

from config import config
import utils
import db
from web.api.auth import forgot, login, register, verify



class UserNotFound(Exception):
    pass


@dataclass
class AuthPayload:
    # user data
    user_id: int
    name: str
    user_created_at: int

    # jwt data
    created_at: int = None
    expires_at: int = None

    # internal data
    validated: bool = False
    api_key: bool = False

@dataclass
class CaptchaPayload:
    # captcha data
    x: str
    "CData, for Turnstile"

    z: str
    "Initial IP address hashed"

    # jwt data
    created_at: int
    expires_at: int

    # internal data
    validated: bool = False

@dataclass
class VerifyPayload:
    # user data
    user_id: int
    type: int
    "0=ip, 1=register, 2=forgot, 3=change_pwd"

    data: str = ""
    "0=ip, 1=None, 2=ip;email, 3=ip"

    # jwt data
    created_at: int = None
    expires_at: int = None

    # internal data
    validated: bool = False

@dataclass
class APIKeyPayload:
    # user data
    user_id: int
    name: str
    user_created_at: int

    # jwt data
    created_at: int = None
    api_key: bool = True

    # internal data
    validated: bool = False

type_dict = {
    0: AuthPayload,
    1: CaptchaPayload,
    2: VerifyPayload,
    3: APIKeyPayload
}


def decode_jwt(token: str, type: int) -> Union[AuthPayload, CaptchaPayload, VerifyPayload, APIKeyPayload, bool]:
    try:
        decoded_value = jwt.decode(token, config().jwt.secret, algorithms=[config().jwt.algor])
    except:
        return False
    else:
        if isinstance(decoded_value, dict):
            try:
                payload = dacite.from_dict(type_dict[type], decoded_value)
            except dacite.DaciteError:
                return False
            else:
                return payload


kickoff_cache: dict[int, int] = {}
api_expire_cache: dict[int, int] = {}


def clean_kickoff_cache(user_id: int) -> None:
    global kickoff_cache
    try:
        del kickoff_cache[user_id]
    except KeyError:
        pass


def clean_api_expire_cache(user_id: int) -> None:
    global api_expire_cache
    try:
        del api_expire_cache[user_id]
    except KeyError:
        pass


def authorise_jwt(token: Union[str, AuthPayload, CaptchaPayload, VerifyPayload, APIKeyPayload], type: int = 0) -> Union[AuthPayload, CaptchaPayload, VerifyPayload, APIKeyPayload, bool]:
    global kickoff_cache, api_expire_cache
    
    if isinstance(token, str):
        payload = decode_jwt(token, type)
    else:
        if token.validated:
            return token
        else:
            payload = token

    if isinstance(payload, AuthPayload) and payload.api_key:
        return payload

    if isinstance(payload, AuthPayload) or (isinstance(payload, VerifyPayload) and getattr(payload, 'type', None) in (2,3)):
        kickoff_time = kickoff_cache.get(payload.user_id)

        if not kickoff_time:
            conn, cur = db.pool.get()
            try:
                cur.execute('SELECT kickoff_time FROM users WHERE id = ?', [payload.user_id])
                kickoff_time = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            if not kickoff_time:
                raise UserNotFound
            
            kickoff_cache[payload.user_id] = kickoff_time[0]

            db.pool.release(conn, cur)
        
        if kickoff_cache[payload.user_id] < payload.created_at and payload.expires_at > utils.ms():
            payload.validated = True
    
    elif isinstance(payload, (CaptchaPayload, VerifyPayload)):
        if payload.expires_at > utils.ms():
            payload.validated = True
    
    elif isinstance(payload, APIKeyPayload):
        api_expire = api_expire_cache.get(payload.user_id)

        if not api_expire:
            conn, cur = db.pool.get()
            try:
                cur.execute('SELECT api_expire FROM users WHERE id = ?', [payload.user_id])
                api_expire = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            if not api_expire:
                raise UserNotFound

            api_expire_cache[payload.user_id] = api_expire[0]

            db.pool.release(conn, cur)
        
        if api_expire_cache[payload.user_id] < payload.created_at:
            payload.validated = True

    return payload


def generate_jwt(payload: Union[AuthPayload, CaptchaPayload, VerifyPayload, APIKeyPayload]) -> str:
    if not payload.created_at:
        payload.created_at = utils.ms()
    
    if not isinstance(payload, APIKeyPayload) and not payload.expires_at:
        if isinstance(payload, AuthPayload):
            payload.expires_at = payload.created_at + config().auth_jwt_expire
        elif isinstance(payload, CaptchaPayload):
            payload.expires_at = payload.created_at + config().turnstile.jwt_expire
        elif isinstance(payload, VerifyPayload):
            payload.expires_at = payload.created_at + config().email.jwt_expire
    
    data = dataclasses.asdict(payload)
    del data['validated']
    
    return jwt.encode(data, config().jwt.secret, config().jwt.algor)


def require_auth(cls):
    @wraps(cls)
    def wrapper(*args, **kwargs):
        jwt = request.headers.get('Authorization')
        if not jwt:
            return jsonify({'error': True, 'message': 'Unauthorized.'}), 401

        jwt_type = 3 if jwt.startswith('Bot') else 0
        jwt = jwt[4:] if jwt_type == 3 else jwt
        
        try:
            payload: Union[AuthPayload, APIKeyPayload] = authorise_jwt(jwt, jwt_type)
        except UserNotFound:
            return jsonify({'error': True, 'message': 'Unauthorized.'}), 401
        
        if not payload or not payload.validated:
            return jsonify({'error': True, 'message': 'Unauthorized.'}), 401

        return cls(payload, *args, **kwargs)
    return wrapper

def no_api_keys(cls):
    @wraps(cls)
    def wrapper(key_payload: Union[AuthPayload, APIKeyPayload], *args, **kwargs):
        if isinstance(key_payload, APIKeyPayload):
            return jsonify({'error': True, 'message': 'API keys are not authorized at this endpoint.'}), 401

        return cls(key_payload, *args, **kwargs)
    return wrapper

from web.api.auth import validate
