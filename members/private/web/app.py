from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_sock import Sock
from werkzeug.exceptions import InternalServerError, NotFound, MethodNotAllowed, BadRequest, UnsupportedMediaType
import time
import traceback

app = Flask(__name__)
sock = Sock(app)

admin_sockets = []

def rate_limit_response(request_limit):
    retry = (int((request_limit.reset_at - time.time()) * 100) / 100)
    return jsonify({
        'error': True,
        'message': f'Rate Limited. Retry in {retry}s',
        'retry_in': retry
    }), 429
    
def rate_limit_key():
    if request.headers.get('Authorization'):
        return request.headers.get('Authorization')
    return request.access_route[0]

limiter = Limiter(
    key_func=rate_limit_key,
    on_breach=rate_limit_response,
    app=app,
    storage_uri="memory://"
)

#@app.before_first_request
#def start_thread():
#    utils.log.info('threads bootup')


@app.after_request
def add_headers(response):
    if limiter.current_limit:
        response.headers["X-RateLimit-Limit"] = limiter.current_limit.limit.amount
        response.headers["X-RateLimit-Remaining"] = limiter.current_limit.remaining - 1
        response.headers["X-RateLimit-Reset-At"] = limiter.current_limit.reset_at
        response.headers["X-RateLimit-Reset-After"] = (int((limiter.current_limit.reset_at - time.time()) * 100) / 100)
    
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"

    return response

def handle_400(e: BadRequest):
    return jsonify({'error': True, 'message': 'Bad Request.'}), 400

def handle_404(e: NotFound):
    return jsonify({'error': True, 'message': '404: Not Found.'}), 404

def handle_405(e: MethodNotAllowed):
    return jsonify({'error': True, 'message': 'Method Not Allowed.'}), 405

def handle_415(e: UnsupportedMediaType):
    return jsonify({'error': True, 'message': 'Malformed or missing JSON body.'}), 400

def handle_500(e: InternalServerError):
    from utils import log
    log.error(traceback.format_exc() + "\n\n" + str(e))
    return jsonify({'error': True, 'message': 'Internal Server Error, please try again.'}), 500


app.register_error_handler(400, handle_400)
app.register_error_handler(404, handle_404)
app.register_error_handler(405, handle_405)
app.register_error_handler(415, handle_415)
app.register_error_handler(500, handle_500)
