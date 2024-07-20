from flask import jsonify, request
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/security', methods=['POST'])
@auth.require_auth
def route_user_security(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    try:
        request_data = {
            'ip_verification':  utils.typ(request.json['ip_verification'], bool)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    if request_data['ip_verification'] is None:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    if request_data['ip_verification']:
        ip_data = utils.jd([request.access_route[0]])
    else:
        ip_data = '0'

    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''UPDATE users SET ips = ? WHERE id = ?;''',
            [ip_data, user_payload.user_id]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    utils.log.debug(f'user {user_payload.user_id} changed IP verification to {request_data["ip_verification"]} from {request.access_route[0]}')

    return jsonify({'error': False}), 200
