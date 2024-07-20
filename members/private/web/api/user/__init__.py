from flask import jsonify
from typing import Union

from web.api.user import keys, orders, payments, activity, security
from web.app import app, limiter
import web.api.auth as auth
from config import config
import oauth
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user', methods=['GET'])
@auth.require_auth
def route_get_user(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT id, name, email, verified, display_name, ips FROM users WHERE id = ?;',
            [user_payload.user_id]
        )
        raw_data = cur.fetchone()

        cur.execute(
            '''SELECT balance FROM payments WHERE user_id = ?
            ORDER BY rowid DESC LIMIT 1;''',
            [user_payload.user_id]
        )
        balance = cur.fetchone()
        if balance is None:
            balance = 0
        else:
            balance = balance[0]
    
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    data = {
        'id': str(raw_data[0]),
        'name': raw_data[1],
        'email': raw_data[2],
        'verified': bool(raw_data[3]),
        'display_name': raw_data[4],
        'balance': balance,
        'created_at': user_payload.user_created_at,
        'ip_verification': False if raw_data[5] == '0' else True,
        'oauth_link': oauth.oauth_link,
        'sellix_product_id': config().sellix.balance_product_id
    }

    return jsonify({'error': False, 'data': data}), 200
