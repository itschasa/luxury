import time
from flask import request, jsonify
import hmac
import hashlib
import traceback

from web.app import app, limiter
from config import config
import utils
import db



def find_user(username: str) -> bool:
    conn, cur = db.pool.get()
    try:
        cur.execute('SELECT id FROM users WHERE name = ?', [username.lower()])
        user = cur.fetchone()
    except db.error as exc:
        app.logger.error(f'error finding user {username} from sellix: {traceback.format_exc()}')
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)
    
    return user[0] if user is not None else None


def add_balance(user_id: int, amount: int, sellix_id: str) -> tuple[int, int]:
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT balance FROM payments WHERE user_id = ? ORDER BY rowid DESC LIMIT 1',
            [user_id]
        )
        balance = cur.fetchone()
        if balance is None: balance = 0
        else: balance = balance[0]
        
        payment_id = utils.snowflake.new()
        cur.execute(
            '''INSERT INTO payments (id, change, user_id, reason, order_id, balance)
            VALUES (?, ?, ?, ?, ?, ?)''',
            [payment_id, amount * 100, user_id, f'Sellix: {sellix_id}', None, balance + (amount * 100)]
        )
    
    except db.error as exc:
        app.logger.error(f'error adding balance to user {user_id} from sellix: {traceback.format_exc()}')
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)
    return balance, balance + (amount * 100)


def check_duplicate_order(sellix_id: str) -> bool:
    "`true` if order is duplicate"
    conn, cur = db.pool.get()
    try:
        cur.execute('SELECT reason FROM payments WHERE reason LIKE ?', [f'%{sellix_id}%'])
        duplicate = cur.fetchone()
    except db.error as exc:
        app.logger.error(f'error checking duplicate order {sellix_id} from sellix: {traceback.format_exc()}')
        db.pool.release(conn, cur)
        raise exc

    db.pool.release(conn, cur)
    return duplicate is not None


def verify_sign(body: bytes, signature: str, ip: str):
    if ip != '99.81.24.41': return False

    h = hmac.new(config().sellix.secret_key.encode(), body, hashlib.sha512)
    return hmac.compare_digest(h.hexdigest().encode(), signature.encode())


def verify_purchase(sellix_type: str, sellix_data: dict):
    if 'order:paid' in sellix_type:
        sellix_id: str = sellix_data['uniqid']
        reasons: list[str] = [f'order_id:{sellix_id}']

        sellix_quantity: int = sellix_data['quantity']
        sellix_product_id: str = sellix_data['product_id']
        
        if sellix_product_id != config().sellix.balance_product_id:
            reasons.append('product_id_mismatch')
        
        try:
            sellix_username: str = sellix_data['custom_fields']['username']
        except:
            reasons.append(f'missing_username')
        else:
            user_id = find_user(sellix_username.lower())
            if user_id is None:
                reasons.append(f'unknown_user:{sellix_username.lower()}')
        
        if check_duplicate_order(sellix_id):
            reasons.append('duplicate_order')

        if len(reasons) > 1:
            return False, reasons
        else:
            balance, new_bal = add_balance(user_id, sellix_quantity, sellix_id)
            reasons.append('success')
            reasons.append(f'balance:{balance}->{new_bal}')
            reasons.append(f'user_id:{user_id}')

            return user_id, reasons
    
    return None, []


@app.route('/api/v1/sellix', methods=['POST'])
@limiter.limit("1 per 5 seconds", deduct_when=lambda response: response.status_code == 401)
def api_sellix():
    if not verify_sign(request.data, request.headers.get('X-Sellix-Signature'), request.access_route[0]):
        return jsonify({'error': True, 'message': "Unauthenticated."}), 401
    
    sellix_data = request.json['data']
    sellix_type = request.json['event']
    
    user = 0
    reasons = []
    try:
        user, reasons = verify_purchase(sellix_type, sellix_data)
    except db.error as exc:
        utils.log.error(f'sellix: {traceback.format_exc()}')
        raise exc

    utils.log.info(f'sellix: user_id={user} type={sellix_type} reasons={reasons}')
    
    return jsonify({'error': False, 'user': user, 'reasons': reasons}), 200
