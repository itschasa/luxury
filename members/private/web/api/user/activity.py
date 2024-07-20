from flask import jsonify
from typing import Union
from collections import OrderedDict

from web.app import app, limiter
import web.api.auth as auth
import oauth
import utils
import db



def get_activity(user_id: int):
    conn, cur = db.pool.get()
    try:
        if user_id == 0:
            sql = '''SELECT id, status, order_data, guild_id, role_ids
            FROM orders;'''
            args = []
        else:
            sql = '''SELECT id, status, order_data, guild_id, role_ids
            FROM orders WHERE user_id = ?;'''
            args = [user_id]
        
        cur.execute(sql, args)
        raw_orders = cur.fetchall()
        order_dict = {order[0]: order for order in raw_orders}
        
        if user_id == 0:
            sql = '''SELECT id, change, reason, order_id, balance
            FROM payments;'''
            args = []
        else:
            sql = '''SELECT id, change, reason, order_id, balance
            FROM payments WHERE user_id = ?;'''
            args = [user_id]

        cur.execute(sql, args)
        raw_payments = cur.fetchall()

        payments: OrderedDict[Union[int, str], Union[list[tuple], tuple]] = {}
        counter = 0
        for payment in raw_payments:
            if payment[3] is None:
                payments[f'x{counter}'] = payment
                counter += 1
            else:
                if payments.get(payment[3]) is None:
                    payments[payment[3]] = [payment]
                else:
                    payments[payment[3]].insert(0, payment)
        
        payments = OrderedDict(reversed(payments.items()))


    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    activity = []
    for order_id, invoices in payments.items():
        if isinstance(order_id, str):
            activity.append({
                'id': str(invoices[0]),
                'type': 'payment',
                'change': invoices[1],
                'reason': invoices[2],
                'balance': invoices[4],
                'created_at': utils.snowflake.time(invoices[0])
            })
        else:
            order = order_dict[order_id]
            activity.append({
                'id': str(order[0]),
                'type': 'order',
                'status': order[1],
                'order_data': utils.jl(order[2]),
                'guild_id': str(order[3]),
                'role_ids': utils.jl(order[4]),
                'created_at': utils.snowflake.time(order[0]),
                'invoices': [{
                    'id': str(invoice[0]),
                    'change': invoice[1],
                    'reason': invoice[2],
                    'balance': invoice[4],
                    'created_at': utils.snowflake.time(invoice[0])
                } for invoice in invoices]
            })
            if order[0] == getattr(oauth.current_order_handle, 'order_id', 0):
                activity[-1]['order_data'] = [{
                    'item_key': item.item_key,
                    'item_name': item.item_name,
                    'quantity': item.quantity,
                    'filled': item.filled,
                    'joins': item.joins,
                    'failed': item.failed
                } for item in oauth.current_order_handle.data.values()]
    
    return activity

@limiter.limit('1 per second')
@limiter.limit('30 per minute')
@app.route('/api/v1/user/activity', methods=['GET'])
@auth.require_auth
def route_get_activity(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    return jsonify({'error': False, 'data': get_activity(user_payload.user_id)}), 200