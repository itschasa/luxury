from main import app, limiter
import utils, config
import database

from flask import request

def create_user_api_key(user_id, db: database.Connection):
    cookie = f'api_{utils.rand_chars(32)}'
    db.insert('cookies', [cookie, user_id, '99999999999', 'null', 'null'])
    return cookie

def delete_user_api_key(user_id, db: database.Connection):
    db.delete('cookies', {}, whereOverRide='cookie LIKE ? AND user = ?', valuesOverRide=[r'%api_%', user_id])

def get_user_api_key(user_id, db: database.Connection):
    results = db.query2('SELECT rowid, cookie FROM cookies WHERE cookie LIKE ? AND user = ?', [r'%api_%', user_id], True)
    if results is None:
        return create_user_api_key(user_id, db)
    else:
        return results[1]

@app.route('/api/v1/users/<url_user>/key', methods=['GET'])
@limiter.limit("1 per 3 seconds", deduct_when=lambda response: response.status_code == 200)
def api_get_key(url_user):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    db = database.Connection(config.db_name)
    res = get_user_api_key(user_id, db)
    db.close()
    return utils.j({'error': False, 'api_key': res}), 200

@app.route('/api/v1/users/<url_user>/key', methods=['DELETE'])
@limiter.limit("1 per 15 seconds", deduct_when=lambda response: response.status_code == 200)
def api_delete_key(url_user):
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    db = database.Connection(config.db_name)
    delete_user_api_key(user_id, db)
    res = get_user_api_key(user_id, db)
    db.close()
    return utils.j({'error': False, 'api_key': res}), 200
