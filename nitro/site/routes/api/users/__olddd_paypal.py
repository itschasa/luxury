from main import app, limiter
import database
import utils, config, mail

import time
from flask import request
import httpx
import json
import time
import config
from datetime import datetime
from datetime import timedelta
import re

f = open('globals/currency.json')
currencies = json.loads(f.read())
f.close()

paypal_token = ('', 0)
paypal_refresh_every = 28800

def remove_special_chars(string):
    allowed_chars = '0123456789.'
    return float(''.join(char for char in string if char in allowed_chars))

def update_currencies():
    global currencies
    current_time = int(time.time())
    
    if currencies['time'] + 86400 < current_time:
        try:
            request = httpx.get('https://open.er-api.com/v6/latest/USD')
            currencies['time'] = current_time
            currencies['data'] = request.json()['rates']
        except:
            pass
        else:
            f = open('globals/currency.json', 'w')
            f.write(json.dumps(currencies, indent=4))
            f.close()

class PayPalError1(Exception):
    pass

class PayPalError2(Exception):
    pass

def fetch_paypal():
    global paypal_token
    
    time_end = datetime.utcnow()
    time_start = time_end + timedelta(days=-30)

    time_start = re.sub(r" +","T",time_start.strftime('%Y-%m-%dT%H:%M:%S.%f'))[:-4] + 'Z'
    time_end = re.sub(r" +","T",time_end.strftime('%Y-%m-%dT%H:%M:%S.%f'))[:-4] + 'Z'
    
    if time.time() > paypal_token[1] + paypal_refresh_every:
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'en_US',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = httpx.post('https://api.paypal.com/v1/oauth2/token',
            headers=headers,
            data='grant_type=client_credentials',
            auth=(config.paypal_client_id, config.paypal_client_secret)
        )
        if response.json().get('access_token') is None:
            raise PayPalError1
        paypal_token = (response.json()['access_token'], int(time.time()))

    headers = {
		'Content-Type': 'application/json',
		'Authorization': 'Bearer ' + paypal_token[0],
	}

    params = (
		('start_date', time_start),
		('end_date', time_end),
		('fields', 'transaction_info, payer_info, shipping_info'),
	)

    response = httpx.get('https://api.paypal.com/v1/reporting/transactions', headers=headers, params=params)
    if response.status_code != 200:
        raise PayPalError2
    data = response.json()
	
    transactions = []
    for d in data['transaction_details']:
        transactions.append(Payment(d))
    
    return transactions

class Payment():
    _minimum_buy = 2
    _base_price = 1
    _bulk_amount = 10
    _bulk_discount = 0.75
    _leeway_amount = 0.05
    _usd_bulk = _bulk_amount * _base_price * _bulk_discount
    _protection_cutoff = 3
    
    def _get_quantity(self):
        if self.usd >= self._usd_bulk:
            return int((self.usd + self._leeway_amount) / self._bulk_discount)
        return int((self.usd + self._leeway_amount) / self._base_price)
    
    def __init__(self, raw_data) -> None:
        self.relavent = False
        if raw_data['transaction_info']['transaction_event_code'] in ['T0000', 'T0011']:
            if '-' not in raw_data['transaction_info']['transaction_amount']['value']:
                self.relavent = True
                self.id = raw_data['transaction_info']['transaction_id']
                self.email = raw_data['payer_info']['email_address']
                self.currency = raw_data['transaction_info']['transaction_amount']['currency_code']
                self.value = float(raw_data['transaction_info']['transaction_amount']['value'])
                # self.fee = 0 if raw_data['transaction_info'].get('fee_amount') is None else float(raw_data['transaction_info'].get('fee_amount').get('value'))
                # ^ not needed currently
                self.usd = int((self.value / currencies['data'][self.currency]) * 100) / 100
                self.quantity = self._get_quantity()
                self.protection = False if raw_data['transaction_info']['protection_eligibility'] == '02' else True
                self.protection_ok = True if self.protection or self.usd <= self._protection_cutoff else False
        
def calculate_payment(quantity: int):
    if quantity < 1:
        return 0

    if quantity >= Payment._bulk_amount:
        return int(quantity * Payment._base_price * Payment._bulk_discount * 100) / 100
    
    return quantity * Payment._base_price


@app.route('/api/v1/users/@me/paypal/calculate', methods=['POST'])
@limiter.limit("2 per 1 second")
def api_user_paypal_calculate():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    try:
        request_data = {
            'quantity': int(request.json['quantity'])
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    price = calculate_payment(request_data['quantity'])
    if price > Payment._protection_cutoff:
        method = 'goods'
    else:
        method = 'friends'
    
    return utils.j({'price': price, 'method': method}), 200


@app.route('/api/v1/users/@me/paypal/check', methods=['POST'])
@limiter.limit("1 per 20 seconds")
def api_user_paypal_check():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    try:
        request_data = {
            'email': request.json['email'].lower()
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if utils.validate_string(request_data['email'], 'email', None, 55) is None:
        return utils.j({'error': True, 'message': "Not a valid email, try again."}), 400

    update_currencies()
    try: transactions = fetch_paypal()
    except PayPalError1: return utils.j({'error': True, 'message': f'Error1: Open a ticket for Support.'}), 500
    except PayPalError2: return utils.j({'error': True, 'message': f'Error2: Open a ticket for Support.'}), 500

    db = database.Connection(config.db_name)
    payment_redeemed = False
    for trans in transactions:
        if trans.relavent:
            if trans.email.lower() == request_data['email']:
                dup_check = db.query('paypal', ['data'], {'id': trans.id}) # data = claimed, 123456 (verify code)
                if dup_check is not None:
                    if dup_check[1] == 'claimed':
                        payment_redeemed = True
                        continue
                
                if trans.protection_ok:
                    if dup_check is None:
                        verify_code = utils.gen_verify_code()
                        mail.send(trans.email, mail.paypal_subject, mail.paypal_content.format(verify_code))
                        db.insert('paypal', [trans.id, f'{verify_code},{trans.quantity}'])

                    db.close()
                    return utils.j({'error': False, 'message': f'Verify your PayPal email to continue.', 'id': trans.id, 'email': f'{trans.email.split("@")[0][:3]}**@{trans.email.split("@")[1]}'}), 200
                else:
                    db.close()
                    return utils.j({'error': True, 'message': 'Payment not made in Goods & Services, open a ticket for support.'}), 409
    
    db.close()
    if payment_redeemed:
        return utils.j({'error': True, 'message': 'All payments have already been claimed.'}), 409
    
    return utils.j({'error': True, 'message': 'Payment Not Found. Please try again in a few minutes.'}), 404

@app.route('/api/v1/users/@me/paypal/verify', methods=['POST'])
@limiter.limit("1 per 3 seconds")
def api_user_paypal_verify():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    try:
        request_data = {
            'id': request.json['id'],
            'code': request.json['code'].replace(' ', '')
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400

    db = database.Connection(config.db_name)
    query = db.query('paypal', ['data'], {'id': request_data['id']})
    if query is None:
        return utils.j({'error': True, 'message': 'Invalid ID.'}), 404
    
    if query[1] == 'claimed':
        return utils.j({'error': True, 'message': 'Payment has already been claimed.'}), 409
    
    code, quantity = query[1].split(',')
    if code == request_data['code']:
        db.edit('paypal', {'data': 'claimed'}, {'id': request_data['id']})
        
        balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [user_id], True)
        if balance is None: balance = 0
        else: balance = balance[0]
        db.insert('credits', [str(quantity), user_id, f'PayPal: {request_data["id"]}', balance+int(quantity), int(time.time())])

        return utils.j({'error': False, 'message': 'Credits redeemed!'}), 200

    return utils.j({'error': False, 'message': 'Invalid Code.'}), 403

@app.route('/api/v1/paypal/webhook/12311', methods=['POST'])
def api_user_paypal_webhook_test():
    f = open('paypal.txt', 'a')
    f.write(f'\n\n\n-------------------\nNEW REQUEST\ntime: {time.time()}\n{request.headers}\n{request.json}')
    f.close()
    return 'ok', 200