from flask import jsonify, request

from web.app import app, limiter
import web.api.auth as auth
import oauth.bot
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('5 per minute')
@app.route('/api/v1/oauth', methods=['POST'])
def route_user_oauth():
    try:
        request_data = {
            'code':      utils.typ(request.json['code'], str),
            'guild_id':  utils.typ(request.json['guild_id'], int),
            'state':     utils.typ(request.json['state'], int)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    conn, cur = db.pool.get()
    try: 
        cur.execute(
            'SELECT guild_id, status FROM orders WHERE id = ?;',
            [request_data['state']]
        )
        order = cur.fetchone()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)
    
    if not order:
        return jsonify({'error': True, 'message': 'Invalid state/order ID.'}), 400
    
    if order[0] != request_data['guild_id']:
        return jsonify({'error': True, 'message': 'Invalid Guild ID, check that you added the bot to the right server, or cancel your order and enter the right guild ID.'}), 400
    
    if order[1] != 0:
        return jsonify({'error': True, 'message': 'Order has already been processed.'}), 400
    
    if (request_data['state'], request_data['guild_id']) in oauth.awaiting_guild_check:
        return jsonify({'error': True, 'message': 'Order is already being processed.'}), 400
    
    oauth.awaiting_guild_check.append((request_data['state'], request_data['guild_id']))
    
    # Worse case scenario, this can fail.
    oauth.bot.handle_oauth_code(request_data['code'])

    return jsonify({'error': False, 'message': 'Order has been queued.'}), 200
