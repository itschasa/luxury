from flask import request
from flask import jsonify
import threading

from web.app import app, limiter
import web.api.admin as admin
import web.api.auth as auth
import oauth
import utils
import db



@limiter.limit('1 per second')
@app.route('/api/v1/admin/tokens', methods=['GET'])
@auth.require_auth
@admin.require_admin
def route_get_tokens(user_payload: auth.AuthPayload):
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT token, user_id, raw_token, status, guild_count, added_on, type, boosts_remaining FROM tokens;'
        )
        raw_data = cur.fetchall()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc

    db.pool.release(conn, cur)

    utils.log.info(f'admin "{user_payload.name}" is fetching {len(raw_data)} token(s)')

    data = [{
        'token':            token[0],
        'user_id':          str(token[1]),
        'raw_token':        token[2],
        'status':           token[3],
        'guild_count':      token[4],
        'added_on':         token[5],
        'type':             token[6],
        'boosts_remaining': token[7]
    } for token in raw_data]

    return jsonify({'error': False, 'data': data}), 200


@limiter.limit('1 per second')
@app.route('/api/v1/admin/tokens', methods=['POST'])
@utils.force_json
@auth.require_auth
@admin.require_admin
def route_load_tokens(user_payload: auth.AuthPayload):
    try:
        request_data = {
            'tokens':   utils.typ(request.json['tokens'], list),
            'type':     oauth.token.TokenTypes(
                            utils.typ(request.json['type'], int)
                        )
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    utils.log.info(f'admin "{user_payload.name}" is importing {len(request_data["tokens"])} token(s) of type "{str(request_data["type"])}"')

    # Import tokens
    threading.Thread(
        target=oauth.token.import_tokens,
        args=(request_data['tokens'], request_data['type']),
        daemon=True
    ).start()

    return jsonify({'error': False}), 200


@limiter.limit('1 per second')
@app.route('/api/v1/admin/tokens', methods=['DELETE'])
@utils.force_json
@auth.require_auth
@admin.require_admin
def route_delete_tokens(user_payload: auth.AuthPayload):
    try:
        request_data = {
            'tokens':   utils.typ(request.json['tokens'], list)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400

    utils.log.info(f'admin "{user_payload.name}" is deleting {len(request_data["tokens"])} token(s)')
    utils.log.debug('tokens to delete: ' + '; '.join(request_data['tokens']))

    # Delete tokens
    conn, cur = db.pool.get()
    try:
        cur.execute(
            f'DELETE FROM tokens WHERE token IN ({", ".join(["?" for _ in request_data["tokens"]])});',
            tuple(request_data['tokens'])
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    return jsonify({'error': False}), 200


@limiter.limit('1 per second')
@app.route('/api/v1/admin/tokens/rescan', methods=['POST'])
@utils.force_json
@auth.require_auth
@admin.require_admin
def route_rescan_tokens(user_payload: auth.AuthPayload):
    try:
        request_data = {
            'tokens':   utils.typ(request.json['tokens'], list)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400

    utils.log.info(f'admin "{user_payload.name}" is rescanning {len(request_data["tokens"])} token(s)')

    # Rescan tokens
    threading.Thread(
        target=oauth.token.rescan_tokens,
        args=(request_data['tokens'],),
        daemon=True
    ).start()

    return jsonify({'error': False}), 200
