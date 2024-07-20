from main import app, limiter, queue
import utils, config
import database

from flask import request
import json
import time

def order_data(user_id):
    db = database.Connection(config.db_name)
    orders = db.query('orders', ['status', 'quantity', 'claim_data', 'timestamp', 'referral'], {'user': user_id}, False)
    orders.sort(key = lambda t: int(t[5]))
    db.close()
    orders_data = []
    
    for order in orders:
        claim_data = json.loads(order[3])
        # [{instance, type, time}, ..]

        if order[1] == 0:
            try: status_text = f"({list(queue.global_queue_data.keys()).index(order[5])}/{len(queue.global_queue_data) - 1})"
            except ValueError: status_text = f"?/{len(queue.global_queue_data) - 1}"
        elif order[1] == 1:
            status_text = f"({len(claim_data)}/{order[2]})"
        else:
            status_text = None

        eta = queue.global_queue_data.get(order[5])
        if eta is None:
            eta = {}
        else:
            eta = eta['eta']

        orders_data.append({
            'id': utils.clean_id(order[5]),
            'status': order[1],
            'quantity': order[2],
            'received': len(claim_data),
            'eta': eta,
            'status_text': status_text,
            'time': order[4],
            'claimed': claim_data
        }) 
    
    return orders_data

@app.route('/api/v1/users/<url_user>/orders', methods=['GET'])
@limiter.limit("2 per 5 seconds", deduct_when=lambda response: response.status_code == 200)
def api_list_orders(url_user):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        db = database.Connection(config.db_name)
        admin_check = db.query('users', ['role'], {'rowid': user_id})
        db.close()
        if admin_check is not None:
            if admin_check[1] != 'User':
                user_id = int(url_user)
        
        if user_id != int(url_user): # check if it was allowed or not
            return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    return utils.j(order_data(user_id)), 200

@app.route('/api/v1/users/<url_user>/orders', methods=['POST'])
@limiter.limit("1 per 3 seconds") # removed deduct_when, because it caused race condition
def api_order_new(url_user):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    try:
        request_data = {
            'token': request.json['token'],
            'quantity': int(request.json['quantity']),
            'anonymous': bool(request.json['anonymous'])
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if request_data['quantity'] < 1:
        return utils.j({'error': True, 'message': "Quantity can't be below 1."}), 400
    
    db = database.Connection(config.db_name)
    total_credits = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [user_id], True)
    if total_credits is None or total_credits[0] < request_data['quantity']:
        db.close()
        return utils.j({'error': True, 'message': "Not enough credits."}), 403
    
    token_valid = utils.check_token(request_data["token"])
    if token_valid != True:
        db.close()
        if token_valid is False:
            return utils.j({'error': True, 'message': "Discord Error, please try again later."}), 403
        return utils.j({'error': True, 'message': token_valid}), 403
    
    time_stamp = int(time.time())

    duplicate_check = db.query2('SELECT quantity, referral FROM orders WHERE user = ? AND token LIKE ? AND status != ?', [user_id, f'%{request_data["token"].replace("%", "").split(".")[0]}%', 2], True)
    if duplicate_check:
        cleaned_order_id = utils.clean_id(duplicate_check[1])
        new_quantity = duplicate_check[0] + request_data['quantity']
        db.insert('credits', [f'-{request_data["quantity"]}', user_id, f"Order #{cleaned_order_id} - Topup ({duplicate_check[0]} -> {new_quantity})", total_credits[0] - request_data['quantity'], time_stamp])
        db.edit("orders", {'quantity': new_quantity}, {'referral': duplicate_check[1]})
        db.close()
        app.logger.info(f"order topup from {user_id} - #{cleaned_order_id} ({duplicate_check[0]} -> {new_quantity})")
        return utils.j({'error': False, 'message': f'Order #{cleaned_order_id} has been topped up! ({duplicate_check[0]} -> {new_quantity})', 'order': cleaned_order_id}), 200

    rand_tmp_seed = utils.rand_chars(16)

    # checks whether to put them at the front of the queue or not, depending if there is anyone else in the queue
    claiming_check = db.query2('SELECT referral FROM orders WHERE status = ? OR status = ?', ['1', '0'], False)
    
    order_id = len(db.query("orders", [], {}, False)) + 1

    if request_data['anonymous']:
        if request.cookies.get('ssid').startswith('api_'):
            anony_mode = 3
        else:
            anony_mode = 1
    else:
        if request.cookies.get('ssid').startswith('api_'):
            anony_mode = 2
        else:
            anony_mode = 0

    db.insert('credits', [f'-{request_data["quantity"]}', user_id, rand_tmp_seed, total_credits[0] - request_data['quantity'], time_stamp])
    db.insert('orders', [
        user_id,
        request_data['quantity'],
        time_stamp,
        0 if len(claiming_check) != 0 else 1,
        '[]',
        str(order_id),
        request_data['token'],
        anony_mode
    ])
    
    cleaned_order_id = utils.clean_id(order_id)
    
    reason = " - " + str(request.json.get("reason", ""))
    if reason == " - ":
        reason = ""
    
    db.edit('credits', {'reason': f'Order #{cleaned_order_id}{reason}'}, {'reason': rand_tmp_seed, 'user': user_id, 'time': time_stamp})
    db.close()
    app.logger.info(f'new order (#{cleaned_order_id}) from {user_id} (api={request.cookies.get("ssid").startswith("api_")})')
    return utils.j({'error': False, 'message': f'Added Order #{cleaned_order_id} to Queue!', 'order': cleaned_order_id}), 200

@app.route('/api/v1/users/<url_user>/orders/<order_id>', methods=['DELETE'])
@limiter.limit("1 per 3 seconds")
def api_order_delete(url_user, order_id):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    db = database.Connection(config.db_name)
    order = db.query2('SELECT referral, quantity, claim_data, token, user, status FROM orders WHERE referral = ?', [int(order_id)], True)
    if order is None:
        return utils.j({'error': True, 'message': 'Invalid Order ID.'}), 400
    
    if str(order[4]) != str(user_id):
        return utils.j({'error': True, 'message': 'Forbidden.'}), 403

    if int(order[5]) == 2:
        return utils.j({'error': True, 'message': 'Order is completed.'}), 403
    
    refund_amount = order[1] - len(json.loads(order[2]))
    
    balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [order[4]], True)
    if balance is None: balance = 0
    else: balance = balance[0]
    
    db.insert('credits', [refund_amount, order[4], f'#{utils.clean_id(order[0])}: Cancelled by User', balance + refund_amount, int(time.time())])
    db.edit('orders', {'quantity': len(json.loads(order[2])), 'status': 2}, {'referral': order[0]})
    utils.trigger_basic_refund(order[0])
    app.logger.info(f'order deleted (#{order_id}) by user={user_id} (api={request.cookies.get("ssid").startswith("api_")})')
    return utils.j({'error': False, 'refund_amount': refund_amount}), 200
