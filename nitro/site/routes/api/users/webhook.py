from main import app, limiter
import utils, config
import database

from flask import request
import json, time, re, httpx

webhook_re = re.compile("^.*(discord|discordapp)\.com\/api\/webhooks\/([0-9]+)\/([a-zA-Z0-9_-]+)$")
emoji_re = re.compile('<(a|):[A-Za-z_-]+:[0-9]+>')

@app.route('/api/v1/users/<url_user>/webhook', methods=['POST'])
@limiter.limit("1 per 10 seconds", deduct_when=lambda response: response.status_code == 200)
def api_webhook_add(url_user):
    user_id = utils.authenticate(request)
    if user_id is False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if url_user != '@me':
        return utils.j({'error': True, 'message': "Forbidden."}), 403

    try:
        request_data = {
            'webhook_id': int(request.json['webhook']['id']),
            'webhook_key': str(request.json['webhook']['key']),
            'message': str(request.json['message']),
            'emojis': dict(request.json['emojis'])
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    
    if '[emoji]' in request_data['message'] and not request_data['emojis']:
        return utils.j({'error': True, 'message': "Data Error, emoji variable used, but no emoji_map provided."}), 400
    
    if not request_data['emojis']:
        available_keys = ['boost', 'classic', 'basic']
        
        for key, value in  request_data['emojis'].items():
            if key not in available_keys:
                return utils.j({'error': True, 'message': "Data Error, invalid emoji_map (invalid key, or duplicate key)."}), 400
            
            if not emoji_re.findall(value):
                return utils.j({'error': True, 'message': f"Data Error, invalid emoji in {value}."}), 400
            
            available_keys.remove(key)
        
        if available_keys:
            return utils.j({'error': True, 'message': f"Data Error, missing emojis: {', '.join(x for x in available_keys)}"}), 400

    webhook_url = f'https://discord.com/api/webhooks/{request_data["webhook_id"]}/{request_data["webhook_key"]}'
    emoji_map = utils.j(request_data['emojis'])
    skip_webhook_check = False
    db = database.Connection(config.db_name)

    res = db.query('webhooks', ['url', 'emojis', 'message'], {'user': user_id})
    if res is not None:
        if res[1] == webhook_url:
            skip_webhook_check = True

            if res[2] == emoji_map and res[3] == request_data['message']:
                db.close()
                return utils.j({"error": False})
    
    if not skip_webhook_check:
        try:
            httpx.get(webhook_url).raise_for_status()
        except:
            db.close()
            return utils.j({"error": True, "message": "Invalid Webhook."})
        
    db.delete('webhooks', {'user': user_id})
    db.insert('webhooks', [user_id, webhook_url, emoji_map, request_data['message']])
    db.close()

    return utils.j({"error": False})