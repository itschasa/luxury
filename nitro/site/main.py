from flask import Flask, request, make_response
from flask_sock import Sock
from flask_limiter import Limiter
import threading
import json
import time

app = Flask(__name__)
sock = Sock(app)

def rate_limit_response(request_limit):
    retry = (int((request_limit.reset_at - time.time()) * 100) / 100)
    return make_response(json.dumps({
        'error': True,
        'message': f'Rate Limited. Retry in {retry}s',
        'retry_in': retry
    }), 429)
    
def rate_limit_key():
    if request.cookies.get('ssid'):
        return request.cookies.get('ssid')
    return request.access_route[0]

limiter = Limiter(
    key_func=rate_limit_key,
    on_breach=rate_limit_response,
    app=app,
    storage_uri="memory://"
)

import database, config
import log_setup
app.logger = log_setup.logger
from routes import assets, templates
from routes.api import queue

from routes.api.users import credits, tickets, orders, key, webhook

from routes.api import sniper
from routes.api import admin, auth, sellix, qr_code, graph, vps
from routes.api.users import _init

import utils

#from routes import rate_limit

@app.before_first_request
def start_thread():
    app.logger.info('threads bootup')

    t1 = threading.Thread(target=tickets.time_to_reply_thread)
    t1.daemon = True
    t1.start()

    t2 = threading.Thread(target=queue.queue_data_thread)
    t2.daemon = True
    t2.start()

    t3 = threading.Thread(target=qr_code.heartbeat_thread)
    t3.daemon = True
    t3.start()

    t4 = threading.Thread(target=sniper.token_check_thread)
    t4.daemon = True
    t4.start()

    t5 = threading.Thread(target=queue.queue_webhook_thread)
    t5.daemon = True
    t5.start()

    t6 = threading.Thread(target=utils.tidy_tokens)
    t6.daemon = True
    t6.start()

    t7 = threading.Thread(target=admin.status_thread)
    t7.daemon = True
    t7.start()

@app.after_request
def add_headers(response):
    if limiter.current_limit:
        response.headers["X-RateLimit-Limit"] = limiter.current_limit.limit.amount
        response.headers["X-RateLimit-Remaining"] = limiter.current_limit.remaining - 1
        response.headers["X-RateLimit-Reset-At"] = limiter.current_limit.reset_at
        response.headers["X-RateLimit-Reset-After"] = (int((limiter.current_limit.reset_at - time.time()) * 100) / 100)
    return response

def handle_404(e):
    return utils.j({'error': True, 'message': '404: Not Found.'}), 404

def handle_405(e):
    return utils.j({'error': True, 'message': 'Method Not Allowed.'}), 405

def handle_500(e):
    return utils.j({'error': True, 'message': 'Internal Server Error.'}), 500


def db_migration_rowid():
    print('> [!!!!!] running migration')
    db = database.Connection(config.db_name)
    orders = db.query("orders", ['referral'], {}, False)
    for order in orders:
        if order[1] == 'null':
            db.edit('orders', {'referral': order[0]}, {'rowid': order[0]})
            print('edited', order[0])
    
    print('> [!!!!!] finished')
    db.close()


app.register_error_handler(404, handle_404)
app.register_error_handler(405, handle_405)
app.register_error_handler(500, handle_500)
