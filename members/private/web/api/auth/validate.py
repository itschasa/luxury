from flask import jsonify
from typing import Union

from web.app import app, limiter
import web.api.auth as auth
import utils



@limiter.limit('1 per second')
@app.route('/api/v1/auth/validate', methods=['GET'])
@auth.require_auth
def route_auth_validate(user_payload: Union[auth.AuthPayload, auth.APIKeyPayload]):
    return jsonify({'error': False}), 200
