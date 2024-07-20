from main import app, limiter
import database
import utils, config

import time
from flask import request
import hmac
import hashlib

def verify_sign(body:bytes, signature, ip):
    if ip != '99.81.24.41': return False

    h = hmac.new(config.sellix_secret_key, body, hashlib.sha512)
    return hmac.compare_digest(h.hexdigest().encode(), signature.encode())

def verify_purchase(sellix_type, sellix_data):
    if sellix_type == 'order:paid':
        sellix_id = sellix_data['uniqid']
        reasons = [f'order_id:{sellix_id}']

        sellix_quantity = sellix_data['quantity']
        sellix_product_id = sellix_data['product_id']
        
        db = database.Connection(config.db_name)
        
        if sellix_product_id not in (config.sellix_product_id, config.sellix_product_id_pp):
            reasons.append('product_id_mismatch')
        
        try:
            sellix_username = sellix_data['custom_fields']['username']
        except:
            reasons.append(f'missing_username')
        else:
            user_id = db.query('users', ['display_name'], {'username': sellix_username.lower()})
            if user_id is None:
                reasons.append(f'unknown_user:{sellix_username.lower()}')
        
        if sellix_data['product_id'] == config.sellix_product_id or sellix_product_id == config.sellix_product_id_pp:
            url = 'https://dash.luxurynitro.com/purchase'
            sellix_data['product_title'] = "Nitro Claim"
        else:
            url = f"https://luxuryboosts.mysellix.io/product/{sellix_data['product_id']}"
        utils.send_order_webhook(f"💸 `{sellix_data['quantity']}x` [`{sellix_data['product_title']}`]({url}) has been bought for `${format(sellix_data['total'], '.2f')}` via `{sellix_data['gateway'].capitalize()}`!")

        if len(reasons) > 1:
            db.close()
            return False, reasons
        else:
            duplicate_check = db.query2('SELECT reason FROM credits WHERE reason LIKE ?', [f'%{sellix_id}%'], True)
            if duplicate_check is not None:
                db.close()
                reasons.append('duplicate_order')
                return False, reasons
            
            balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [user_id[0]], True)
            if balance is None: balance = 0
            else: balance = balance[0]
            db.insert('credits', [str(sellix_quantity), user_id[0], f'Sellix: {sellix_id}', balance+sellix_quantity, int(time.time())])
            db.close()
            reasons.append('success')
            return f'{user_id[1]}:{user_id[0]}', reasons
    return None, []

def format_message(msg:str) -> list:
    words = msg.split(' ')
    msg_formatted = ['']
    max_char_count = 40
    for word in words:
        if len(msg_formatted[-1] + word) > max_char_count:
            msg_formatted.append('')
        msg_formatted[-1] += word + ' '
    
    return '\n> ' + '\n> '.join(msg_formatted)

def check_feedback(sellix_type, sellix_data, reasons:list):
    if sellix_type == 'feedback:received':
        message = sellix_data['message']
        stars = sellix_data['score']
        product_title = sellix_data['product']['title']
        product_id = sellix_data['product']['uniqid']
        
        message = format_message(message)
        message = f"{'<:AHHH:1135941348416037004>'*stars} on [`{product_title}`](https://luxuryboosts.mysellix.io/product/{product_id}):{message}"
        utils.send_feedback_webhook(message)
        reasons.append("feedback_added")
    return reasons
        
        

@app.route('/api/v1/sellix', methods=['POST'])
@limiter.limit("1 per 5 seconds", deduct_when=lambda response: response.status_code == 401)
def api_sellix():
    if verify_sign(request.data, request.headers.get('X-Sellix-Signature'), request.access_route[0]) == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    sellix_data = request.json['data']
    sellix_type = request.json['event']

    user, reasons = verify_purchase(sellix_type, sellix_data)
    reasons = check_feedback(sellix_type, sellix_data, reasons)
    app.logger.info(f'sellix: {user} {sellix_type} {reasons}')
    
    return utils.j({'error': False, 'user': user, 'reasons': reasons}), 200
    
