from main import app, limiter
import utils, config
import database
from main import tickets, orders, sniper, queue

from flask import request
import json, time

news_data = (0, None)

@app.route('/api/v1/users/<url_user>', methods=['GET'])
@limiter.limit("5 per 6 seconds", deduct_when=lambda response: response.status_code == 200)
def api_user_data(url_user):
    global news_data
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    db = database.Connection(config.db_name)
    if url_user != '@me':
        admin_check = db.query('users', ['role'], {'rowid': user_id})
        if admin_check is not None:
            if admin_check[1] != 'User':
                user_id = int(url_user)
        
        if user_id != int(url_user): # check if it was allowed or not
            db.close()
            return utils.j({'error': True, 'message': "Forbidden."}), 403

    user_data = db.query('users', ['username', 'display_name', 'email', 'role'], {'rowid': user_id})
    credit_data = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [user_id], True)
    db.close()

    if user_data is None:
        return utils.j({'error': True, 'message': "Unknown User."}), 400
    
    if credit_data is None:
        credit_data = [0]

    current_time = int(time.time())
    if news_data[0] + 10 < current_time:
        f = open('globals/news.txt')
        news_file_content = f.read()
        if news_file_content != 'null':
            news_data = (current_time, news_file_content)
        else:
            news_data = (current_time, None)
        f.close()
    
    return utils.j({
        "id": user_data[0],
        "email": user_data[3],
        "username": user_data[1],
        "display_name": user_data[2],
        "credits": credit_data[0],
        "tickets": tickets.ticket_data(user_data[0], user_data[4]),
        "orders": orders.order_data(user_data[0]),
        "stats": {
            "alts": sniper.alts,
            "servers": sniper.servers,
            "support_time": tickets.time_to_reply,
            "total_claims": 3139 + queue.global_claims_count, # 3139 was before it was website
            "boost_percent": queue.global_boost_percent,
            "basic_percent": queue.global_basic_percent,
            "classic_percent": queue.global_classic_percent
        },
        'news': news_data[1]
    }), 200