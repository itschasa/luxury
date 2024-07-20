from flask import request
from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
from config import config
import utils
import db
import oauth



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/orders', methods=['GET'])
@auth.require_auth
def route_get_orders(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''SELECT id, status, order_data, guild_id, role_ids
            FROM orders WHERE user_id = ?;''',
            [user_payload.user_id]
        )
        raw_data = cur.fetchall()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)
    
    data = []
    for order in raw_data:
        data.append({
            'id': order[0],
            'status': order[1],
            'order_data': utils.jl(order[2]),
            'guild_id': order[3],
            'role_ids': utils.jl(order[4]),
            'created_at': utils.snowflake.time(order[0])
        })
        
        if order[0] == getattr(oauth.current_order_handle, 'order_id', 0):
            data[-1]['order_data'] = [{
                'item_key': item.item_key,
                'item_name': item.item_name,
                'quantity': item.quantity,
                'filled': item.filled,
                'joins': item.joins,
                'failed': item.failed
            } for item in oauth.current_order_handle.data.values()]
    
    return jsonify({'error': False, 'data': data}), 200


@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/orders', methods=['POST'])
@utils.force_json
@auth.require_auth
def route_new_order(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    try:
        request_data = {
            'order':     utils.typ(request.json['order'], dict),
            'guild_id':  utils.typ(request.json['guild_id'], int),
            'role_ids':  utils.typ(request.json['role_ids'], list)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400

    # Validate order, and calculate cost
    order = []
    cost = 0
    for key, quantity in request_data['order'].items():
        try:
            key = int(key)
        except:
            return jsonify({'error': True, 'message': 'Invalid item.'}), 400
        
        if not isinstance(quantity, int):
            return jsonify({'error': True, 'message': 'Invalid quantity (not an integer).'}), 400
        
        if quantity == 0:
            continue
        
        elif quantity < 0:
            return jsonify({'error': True, 'message': 'Invalid quantity (negative).'}), 400
        
        item = oauth.token.TokenTypes(key)
        if not item:
            return jsonify({'error': True, 'message': 'Invalid item.'}), 400
        else:
            order.append((key, quantity))
            cost += quantity * item.cost
    
    if len(order) == 0:
        return jsonify({'error': True, 'message': 'No items in order.'}), 400
    
    # Sort order by key, to help detect duplicates
    order.sort(key=lambda x: x[0])
    
    tmp = []
    for role_id in request_data['role_ids']:
        try:
            role_id = int(role_id)
        except:
            return jsonify({'error': True, 'message': 'Invalid role.'}), 400
        else:
            tmp.append(role_id)
    request_data['role_ids'] = tmp

    # Check if user has enough money
    conn, cur = db.pool.get()
    try:
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
    
    if balance < cost:
        return jsonify({'error': True, 'message': f'Insufficient funds. Need ${(cost-balance)/10000} more.'}), 400
    
    # Check if there's enough stock
    for key, quantity in order:
        item = oauth.token.TokenTypes(key)
        
        if not oauth.token.pre_check_search(item, quantity, request_data['guild_id']):
            return jsonify({'error': True, 'message': f'Insufficient stock for {str(item)}.'}), 400

    try:
        cur.execute(
            '''SELECT id FROM orders WHERE user_id = ? AND status = 0 AND order_data = ?;''',
            [user_payload.user_id, utils.jd(order)]
        )
        dup_orders = cur.fetchone()
    except:
        db.pool.release(conn, cur)
        raise exc
    
    if dup_orders is not None:
        return jsonify({'error': True, 'message': 'Duplicate order, please complete your previous order by adding our Bot to your server.'}), 400

    # Create order
    current_time = utils.ms()
    order_id = utils.snowflake.new(current_time)
    payment_id = utils.snowflake.new(current_time)

    try:
        cur.execute(
            '''INSERT INTO payments (id, change, user_id, reason, order_id, balance)
            VALUES (?, ?, ?, ?, ?, ?);''',
            [payment_id, -cost, user_payload.user_id, f'Order #{order_id}{"" if isinstance(user_payload, auth.AuthPayload) else " (API)"}', order_id, balance - cost]
        )

        cur.execute(
            '''INSERT INTO orders (id, status, user_id, order_data, guild_id, role_ids)
            VALUES (?, ?, ?, ?, ?, ?);''',
            [order_id, 0, user_payload.user_id, utils.jd(order), request_data['guild_id'], utils.jd(request_data['role_ids'])]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc

    db.pool.release(conn, cur)

    utils.log.info(f'new order {order_id} created by {user_payload.user_id}{"" if isinstance(user_payload, auth.AuthPayload) else " (API)"} for ${cost/10_000}')
    
    return jsonify({'error': False, 'message': 'Order has been created!', 'order_id': str(order_id), 'oauth_link': oauth.oauth_link + f'&state={order_id}'}), 200


@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/orders/costs', methods=['GET'])
@auth.require_auth
def route_get_costs(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    return jsonify({'error': False, 'costs': {
        str(item): oauth.token.TokenTypes(item).cost for item in list(oauth.token.token_types_dict.keys())
    }}), 200


@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/user/orders/<int:order_id>', methods=['DELETE'])
@auth.require_auth
def route_cancel_order(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload], order_id: int):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''SELECT status, user_id, guild_id, order_data FROM orders WHERE id = ?;''',
            [order_id]
        )
        order_data = cur.fetchone()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    if order_data is None:
        return jsonify({'error': True, 'message': 'Order not found.'}), 404
    
    elif order_data[1] != user_payload.user_id:
        return jsonify({'error': True, 'message': 'Forbidden.'}), 403
    
    elif order_data[0] != 0:
        return jsonify({'error': True, 'message': 'Order has already been processed.'}), 400
    
    elif order_id in list(oauth.join_queue.queue):
        return jsonify({'error': True, 'message': 'Order is being proccessed.'}), 400
    
    order_data_db = utils.jl(order_data[3]) # [[key,quantity]]
    
    price = 0
    new_order_data = []
    for item in order_data_db:
        price += item[1] * oauth.token.TokenTypes(item[0]).cost
        new_order_data.append({
            "item_key": item[0],
            "item_name": str(oauth.token.TokenTypes(item[0])),
            "quantity": item[1],
            "filled": 0,
            "joins": 0,
            "failed": 0
        })

    try:
        cur.execute(
            '''UPDATE orders SET status = 2, order_data = ?
            WHERE id = ?;''',
            [utils.jd(new_order_data), order_id]
        )

        cur.execute(
            '''SELECT balance FROM payments WHERE user_id = ?
            ORDER BY rowid DESC LIMIT 1;''',
            [user_payload.user_id]
        )
        balance: Union[tuple[int], None] = cur.fetchone()
        if balance is None:
            balance = 0
        else:
            balance = balance[0]
        
        payment_id = utils.snowflake.new()

        cur.execute(
            '''INSERT INTO payments (id, change, user_id, reason, order_id, balance)
            VALUES (?, ?, ?, ?, ?, ?);''',
            [payment_id, price, user_payload.user_id, f'Order #{order_id} cancelled by User{"" if isinstance(user_payload, auth.AuthPayload) else " (via API)"}.', order_id, balance + price]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    if (order_id, order_data[2]) in oauth.awaiting_guild_check:
        oauth.awaiting_guild_check.remove((order_id, order_data[2]))

    db.pool.release(conn, cur)
    
    utils.log.info(f'order {order_id} cancelled by {user_payload.user_id}{"" if isinstance(user_payload, auth.AuthPayload) else " (API)"}')
    
    return jsonify({'error': False, 'message': 'Order has been cancelled!'}), 200
