from flask import jsonify, request
from typing import Union
import os

from web.app import app, limiter, sock, admin_sockets
import web.api.admin as admin
import web.api.auth as auth
from config import config
import utils



@limiter.limit('1 per second')
@app.route('/api/v1/admin/logs', methods=['GET'])
@auth.require_auth
@admin.require_admin
def route_get_logs(user_payload: auth.AuthPayload):
    logs = []
    for log in os.listdir('logs'):
        logs.append(log)

    return jsonify({'error': False, 'data': logs}), 200


@limiter.limit('1 per second')
@app.route('/api/v1/admin/logs/fetch/<log_name>', methods=['GET'])
@auth.require_auth
@admin.require_admin
def route_get_log(user_payload: auth.AuthPayload, log_name: str):
    if not os.path.isfile(f'logs/{log_name}'):
        return jsonify({'error': True, 'message': 'Log not found.'}), 404

    with open(f'logs/{log_name}', 'r') as f:
        log = f.read()

    return jsonify({'error': False, 'data': log}), 200


@sock.route('/api/v1/admin/logs/ws')
def route_get_log_ws(ws):
    jwt = message = ws.receive(timeout=10)
    if not jwt:
        ws.send('Unauthorized.')
        ws.close(); return

    jwt_type = 3 if jwt.startswith('Bot') else 0
    jwt = jwt[4:] if jwt_type == 3 else jwt
    
    try:
        key_payload: Union[auth.AuthPayload, auth.APIKeyPayload] = auth.authorise_jwt(jwt, jwt_type)
    except auth.UserNotFound:
        ws.send('Unauthorized.')
        ws.close(); return
    
    if not key_payload or not key_payload.validated:
        ws.send('Unauthorized.')
        ws.close(); return

    if key_payload.user_id not in config().admins:
        ws.send('Unauthorized.')
        ws.close(); return
    
    if isinstance(key_payload, auth.APIKeyPayload):
        ws.send('No API Keys allowed.')
        ws.close(); return

    admin_sockets.append(ws)

    utils.log.debug(f'admin "{key_payload.name}" connected to logs websocket')

    while True:
        message = ws.receive()
        if message is not None:
            pass
        else:
            break

    try:
        admin_sockets.remove(ws)
    except:
        pass

    ws.close()
