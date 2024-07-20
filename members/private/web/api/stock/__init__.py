from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
import oauth
import utils



cached_stock: dict[int, int] = {}
last_stock_update: int = 0

@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/stock', methods=['GET'])
@auth.require_auth
def route_get_stock(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    global last_stock_update
    
    if last_stock_update + 30_000 < utils.ms():
        for type_key in oauth.token.token_types_dict.keys():
            cached_stock[type_key] = oauth.token.get_stock_quantity(oauth.token.TokenTypes(type_key))
        
        last_stock_update = utils.ms()

    return jsonify({'error': False, 'data': cached_stock}), 200
