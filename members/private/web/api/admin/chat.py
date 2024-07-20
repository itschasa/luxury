from flask import request
from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.admin as admin
import web.api.auth as auth
from oauth.token import TokenTypes
import config
import utils
import db



@limiter.limit('1 per second')
@app.route('/api/v1/admin/chat', methods=['POST'])
@auth.require_auth
@admin.require_admin
def route_post_chat(user_payload: auth.AuthPayload):
    try:
        request_data = {
            'command': utils.typ(request.json['command'], str)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400


    current_time = utils.ms()
    return_message = {'error': False, 'reply': 'Command not found.'} #, 'jwt': ''}

    help_data = {
        'help': '/help - Display this message.',
        'lookup': '/lookup [query] - Find a user based on IP, username, or email.',
        'balance': '/balance [user id] [DOLLARS] [reason] - Add/remove balance from a user IN DOLLARS, use decimals if needed.',
        'login': '/login [user id] - Login to a different account, from user id.',
        'user': '/user [user id] - Display orders, info, tickets, and credits history of that user.',
        'emailfix': "/emailfix [user id] [new email] - Changes and verifies a user's email.",
        'cancelorder': '/cancelorder [order id] [refund] - Cancels an order, refund can be true, or int.',
        'refreshconfig': '/refreshconfig - Refreshes the config file.',
        'order': '/order [order id] - Display info about an order.',
        'payment': '/payment [payment id] - Display info about a payment.'
    }

    conn, cur = db.pool.get()
    
    if request_data['command'].startswith('/lookup'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'data': ' '.join(x for x in command_args[1:])
            }
        except:
            return_message['reply'] = help_data["delorder"]
        else:
            try:
                cur.execute(
                    '''SELECT id, name, email, ips, verified, kickoff_time, display_name, api_expire FROM users
                    WHERE name LIKE ? OR email LIKE ? OR ips LIKE ?;''',
                    [f"%{command_data['data']}%", f"%{command_data['data']}%", f"%{command_data['data']}%"]
                )
                raw_data = cur.fetchall()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            return_message['reply'] = f'Found {len(raw_data)} user(s):'
            for user in raw_data:
                return_message['reply'] += f'\n{user[0]}\n- Username: {user[1]}\n- Email: {user[2]}\n- IPs: {user[3]}\n- Verified: {user[4]}\n- Last_PWD_Reset: {user[5]}\n- Display Name: {user[6]}\n- Last_API_Reset: {user[7]}\n\n'

    elif request_data['command'].startswith('/balance'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user_id': int(command_args[1]),
                'quantity': int(float(command_args[2]) * 10_000),
                'reason': ' '.join(x for x in command_args[3:])
            }
        except:
            return_message['reply'] = help_data["balance"]
        else:
            try:
                cur.execute(
                    '''SELECT balance FROM payments WHERE user_id = ?
                    ORDER BY rowid DESC LIMIT 1;''',
                    [command_data['user_id']]
                )
                balance: Union[tuple[int], None] = cur.fetchone()
                if balance is None:
                    balance = 0
                else:
                    balance = balance[0]
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            payment_id = utils.snowflake.new(current_time)

            try:
                cur.execute(
                    '''INSERT INTO payments (id, change, user_id, reason, order_id, balance)
                    VALUES (?, ?, ?, ?, ?, ?);''',
                    [payment_id, command_data['quantity'], command_data['user_id'], command_data['reason'], None, balance + command_data['quantity']]
                )
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            return_message['reply'] = f'Updated balance of user {command_data["user_id"]} from {balance} to {balance + command_data["quantity"]} (Payment ID: {payment_id}).'

    elif request_data['command'].startswith('/login'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user_id': int(command_args[1])
            }
        except:
            return_message['reply'] = help_data["login"]
        else:
            try:
                cur.execute(
                    '''SELECT id, display_name FROM users
                    WHERE id = ?;''',
                    [command_data['user_id']]
                )
                user = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            if user is None:
                return_message['reply'] = f'User {command_data["user_id"]} not found.'
            else:
                return_message['reply'] = f'Logged in as {user[1]} (ID: {user[0]}). Refresh the page.'
                return_message['jwt'] = auth.generate_jwt(
                    auth.AuthPayload(
                        user_id=user[0],
                        name=user[1],
                        user_created_at=utils.snowflake.time(user[0])
                    )
                )
    
    elif request_data['command'].startswith('/user'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user_id': int(command_args[1])
            }
        except:
            return_message['reply'] = help_data["user"]
        else:
            try:
                cur.execute(
                    '''SELECT id, name, email, ips, verified, kickoff_time, display_name, api_expire FROM users
                    WHERE id = ?;''',
                    [command_data['user_id']]
                )
                user = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            if user is None:
                return_message['reply'] = f'User {command_data["user_id"]} not found.'
            else:
                return_message['reply'] = f'\nUser {user[1]}\n- ID: {user[0]}\n- Email: {user[2]}\n- IPs: {user[3]}\n- Verified: {user[4]}\n- Last_PWD_Reset: {user[5]}\n- Display Name: {user[6]}\n- Last_API_Reset: {user[7]}'

    elif request_data['command'].startswith('/emailfix'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user_id': int(command_args[1]),
                'new_email': command_args[2]
            }
        except:
            return_message['reply'] = help_data["emailfix"]
        else:
            try:
                cur.execute(
                    '''UPDATE users SET email = ?, verified = 1 WHERE id = ?;''',
                    [command_data['new_email'], command_data['user_id']]
                )
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            return_message['reply'] = f'Updated email of user {command_data["user_id"]} to {command_data["new_email"]}.'
    
    elif request_data['command'].startswith('/help'):
        return_message['reply'] = 'Available commands:'
        for command in help_data.keys():
            return_message['reply'] += f'\n{help_data[command]}'
    
    elif request_data['command'].startswith('/cancelorder'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'order_id': int(command_args[1]),
                'refund': command_args[2].lower()
            }
        except:
            return_message['reply'] = help_data["cancelorder"]
        else:
            try:
                cur.execute(
                    '''SELECT user_id, status, order_data FROM orders
                    WHERE id = ?;''',
                    [command_data['order_id']]
                )
                order = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            
            if order is None:
                return_message['reply'] = f'Order {command_data["order_id"]} not found.'
            elif order[1] == 2:
                return_message['reply'] = f'Order {command_data["order_id"]} is already completed.'
            
            else:
                order_data = utils.jl(order[2]) # [[key,quantity]]
                
                price = 0
                new_order_data = []
                for item in order_data:
                    price += item[1] * TokenTypes(item[0]).cost
                    new_order_data.append({
                        "item_key": item[0],
                        "item_name": str(TokenTypes(item[0])),
                        "quantity": item[1],
                        "filled": 0,
                        "joins": 0,
                        "failed": 0
                    })

                try:
                    cur.execute(
                        '''UPDATE orders SET status = 2, order_data = ?
                        WHERE id = ?;''',
                        [utils.jd(new_order_data), command_data['order_id']]
                    )

                    cur.execute(
                        '''SELECT balance FROM payments WHERE user_id = ?
                        ORDER BY rowid DESC LIMIT 1;''',
                        [order[0]]
                    )
                    balance: Union[tuple[int], None] = cur.fetchone()
                    if balance is None:
                        balance = 0
                    else:
                        balance = balance[0]

                    if command_data['refund'] != 'true':
                        price = int(command_data['refund'])
                    
                    payment_id = utils.snowflake.new(current_time)

                    cur.execute(
                        '''INSERT INTO payments (id, change, user_id, reason, order_id, balance)
                        VALUES (?, ?, ?, ?, ?, ?);''',
                        [payment_id, price, order[0], f'Order {command_data["order_id"]} cancelled by Admin.', command_data['order_id'], balance + price]
                    )
                except db.error as exc:
                    db.pool.release(conn, cur)
                    raise exc
                
                return_message['reply'] = f'Cancelled order {command_data["order_id"]} and refunded ${int(price/10_000)} ({payment_id}).'
    
    elif request_data['command'].startswith('/refreshconfig'):
        config.config(True)
        utils.log.info(f'config was reloaded by admin "{user_payload.name}"')
        return_message['reply'] = f'Config reloaded!'

    elif request_data['command'].startswith('/order'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'orderid': ' '.join(x for x in command_args[1:])
            }
        except:
            return_message['reply'] = help_data["order"]
        else:
            try:
                cur.execute(
                    '''SELECT id, status, user_id, order_data, guild_id, role_ids FROM orders
                    WHERE id = ?;''',
                    [command_data['orderid']]
                )
                order = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            else:
                if order is None:
                    return_message['reply'] = f'Order {command_data["orderid"]} not found.'
                else:
                    return_message['reply'] = f'\nOrder {command_data["orderid"]}:\n- Status: {order[1]}\n- User ID: {order[2]}\n- Data: {order[3]}\n- Guild ID: {order[4]}\n- Role IDs: {order[5]}'

    elif request_data['command'].startswith('/payment'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'paymentid': ' '.join(x for x in command_args[1:])
            }
        except:
            return_message['reply'] = help_data["payment"]
        else:
            try:
                cur.execute(
                    '''SELECT id, change, user_id, reason, order_id, balance FROM payments
                    WHERE id = ?;''',
                    [command_data['paymentid']]
                )
                payment = cur.fetchone()
            except db.error as exc:
                db.pool.release(conn, cur)
                raise exc
            else:
                if payment is None:
                    return_message['reply'] = f'Payment {command_data["paymentid"]} not found.'
                else:
                    return_message['reply'] = f'\nPayment {command_data["paymentid"]}:\n- Change: {payment[1]}\n- User ID: {payment[2]}\n- Reason: {payment[3]}\n- Order ID: {payment[4]}\n- Balance: {payment[5]}'

    db.pool.release(conn, cur)

    return jsonify(return_message), 200
