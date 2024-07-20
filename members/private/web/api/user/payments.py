from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/payments', methods=['GET'])
@auth.require_auth
def route_get_payments(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''SELECT id, change, user_id, reason, order_id, balance
            FROM payments WHERE user_id = ?;''',
            [user_payload.user_id]
        )
        raw_data = cur.fetchall()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    data = [{
        'id': str(payment[0]),
        'change': payment[1],
        'user_id': str(payment[2]),
        'reason': payment[3],
        'order_id': str(payment[4]),
        'balance': payment[5],
        'created_at': utils.snowflake.time(payment[0])
    } for payment in raw_data]

    return jsonify({'error': False, 'data': data}), 200
