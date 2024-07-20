from main import app, limiter
import utils, config
import database

from flask import request

def credit_data(user_id):
    db = database.Connection(config.db_name)
    credits = db.query('credits', ['change', 'reason', 'balance', 'time'], {'user': user_id}, False)
    db.close()
    credits_history = []
    closing_balance = 0
    
    for credit in credits:
        credits_history.append({
            'id': utils.clean_id(credit[0]),
            'change': credit[1],
            'time': credit[4],
            'reason': credit[2],
            'closing_balance': credit[3]
        })
        closing_balance = credit[3]
    
    
    credits_history.reverse()
    return {"total": closing_balance, "history": credits_history}


@app.route('/api/v1/users/<url_user>/credits', methods=['GET'])
@limiter.limit("2 per 5 seconds", deduct_when=lambda response: response.status_code == 200)
def api_credit_data(url_user):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    
    if url_user != '@me':
        db = database.Connection(config.db_name)
        admin_check = db.query('users', ['role'], {'rowid': user_id})
        if admin_check is not None:
            if admin_check[1] != 'User':
                user_id = int(url_user)
        
        if user_id != int(url_user): # check if it was allowed or not
            db.close()
            return utils.j({'error': True, 'message': "Forbidden."}), 403
        
        db.close()
    
    return utils.j(credit_data(user_id)), 200
