from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('5 per minute')
@app.route('/api/v1/user/keys', methods=['POST'])
@auth.require_auth
def route_new_key(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    if isinstance(user_payload, auth.APIKeyPayload):
        return jsonify({'error': True, 'message': 'API keys cannot be used to create new keys.'}), 403

    key_jwt = auth.generate_jwt(
        auth.APIKeyPayload(
            user_payload.user_id,
            user_payload.name,
            user_payload.user_created_at
        )
    )

    utils.log.debug(f'user {user_payload.user_id} created a new API key')

    return jsonify({'error': False, 'key': key_jwt}), 200


@limiter.limit('1 per second')
@limiter.limit('3 per minute')
@app.route('/api/v1/user/keys', methods=['DELETE'])
@auth.require_auth
def route_delete_keys(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'UPDATE users SET api_expire = ? WHERE id = ?;',
            [utils.ms(), user_payload.user_id]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    auth.clean_api_expire_cache(user_payload.user_id)

    utils.log.debug(f'user {user_payload.user_id} deleted all API keys')

    return jsonify({'error': False}), 200
