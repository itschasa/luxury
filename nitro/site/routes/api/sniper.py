from main import app, limiter
import utils, config, database

import time, json, httpx, random, base64, pycurl, io, traceback
import threading
from flask import request

sniper_translation = {
    "Nitro Basic Monthly": "Basic Monthly",
    "Nitro Basic Yearly": "Basic Yearly",
    "Nitro Monthly": "Boost Monthly",
    "Nitro Yearly": "Boost Yearly",
    "Nitro Classic Monthly": "Classic Monthly",
    "Nitro Classic Yearly": "Classic Yearly",
}

instances = {}
alts = 0
servers = 0

proccess_hit_lock = threading.Lock()

def token_check_thread():
    while True:
        db = database.Connection(config.db_name)
        orders = db.query2('SELECT referral, quantity, claim_data, token, user, status FROM orders WHERE status != ?', ['2'], False)
        refunded = []
        for order in orders:
            if utils.check_token(order[3]) not in [True, False]:
                if order[0] not in refunded:
                    refund_amount = order[1] - len(json.loads(order[2]))
                    balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [order[4]], True)
                    if balance is None: balance = 0
                    else: balance = balance[0]
                    db.insert('credits', [refund_amount, order[4], f'Token was Invalid on Order #{utils.clean_id(order[0])}', balance + refund_amount, int(time.time())])
                    db.edit('orders', {'quantity': len(json.loads(order[2])), 'status': 2}, {'referral': order[0]})
                    utils.trigger_basic_refund(order[0])
                    app.logger.info(f'token invalid on order {order[0]}')
                    refunded.append(order[0])

            else: # token valid
                if order[5] != 1:
                    db.edit('orders', {'status': 1}, {'referral': order[0]})
                break
        db.close()
        time.sleep(300)

def process_hit(db: database.Connection, instance_id:str, request_data:dict):
    current_order = db.query2('SELECT referral, quantity, claim_data, token, anonymous, user, status, timestamp, rowid FROM orders WHERE status != ? AND token = ?', ['2', request_data['token']], True)
    if current_order is not None:
        current_order_data: list = json.loads(current_order[2])
        current_order_data.append({
            "instance": instance_id,
            "time": int(time.time()),
            "type": sniper_translation[request_data["snipe"]],
            "snipe_time": request_data["time"]
        })
        
        if len(current_order_data) >= current_order[1]:
            # order completed
            order_status = 2
            if current_order[6] == 1:
                next_order = db.query('orders', [], {'status': 0}, True)
                if next_order:
                    db.edit('orders', {'status': 1}, {'rowid': next_order[0]})
        
        elif "Boost" in sniper_translation[request_data["snipe"]]:
            # order just received boost nitro, return them to back of queue, if theres anymore queue
            res = db.query('orders', [], {'status': 0}, True) # second order in queue
            if res and current_order[6] == 1:
                order_status = 0
                db.edit('orders', {'status': 1}, {'rowid': res[0]})
                db.delete('orders', {'rowid': current_order[8]})
                db.insert('orders', [current_order[5], current_order[1], current_order[7], current_order[6], current_order[2], current_order[0], current_order[3], current_order[4]])
            else:
                order_status = 1
            
        else:
            # order not completed, and boost nitro not received, continue at front of queue
            order_status = 1
        
        db.edit('orders', {'status': order_status, 'claim_data': json.dumps(current_order_data)}, {'referral': current_order[0]})
        if order_status == 2:
            utils.trigger_basic_refund(current_order[0])
    
        app.logger.info(f'snipe on {current_order[0]}: {sniper_translation[request_data["snipe"]]}')

        # reseller webhook attempt
        res = db.query('webhooks', ['url', 'emojis', 'message'], {'user': current_order[5]})
        if res:
            emoji_map = json.loads(res[2])

            try: 
                httpx.post(res[1], json={'content':
                    res[3]
                        .replace('[emoji]', emoji_map[sniper_translation[request_data["snipe"]].split(' ')[0].lower()])
                        .replace('[nitro]', sniper_translation[request_data["snipe"]])
                        .replace('[user]', 'Anonymous' if current_order[4] in (1, 3) else f"<@{str(base64.b64decode(bytes(request_data['token'].split('.')[0] + '==', encoding='utf-8')), encoding='utf-8')}>")
                        .replace('[order]', f'#{utils.clean_id(current_order[0])}')
                        .replace('[claimed]', str(len(json.loads(current_order[2])) + 1))
                        .replace('[quantity]', str(current_order[1]))
                        .replace('[time]', str(request_data["time"]))
                })
            except: app.logger.warn(f'failed to send resell webhook: {traceback.format_exc()}')
        else:
            app.logger.warn(f'no resell webhook found on order {current_order[0]}')
    
    else:
        # if it was given to some other token for some reason, just let it be and dont charge current customer for our mistake...
        app.logger.info(f'snipe on unknown order: {request_data}')

    # discord server webhook
    try:
        emoji = '<:nitro_boost:1093986192346849310>' if 'Boost' in sniper_translation[request_data["snipe"]] else '<:nitro_basic:1093984571839758417>' if "Basic" in sniper_translation[request_data["snipe"]] else "<:nitro_classic:1129332873728634970>"
        discord_id = '<@' + str(base64.b64decode(bytes(request_data["token"].split('.')[0] + '==', encoding='utf-8')), encoding='utf-8') + '>'
        if current_order is None:
            order_id = 'null'
            progress = 'x/x'
        else:
            order_id = utils.clean_id(current_order[0])
            progress = f'{len(json.loads(current_order[2])) + 1}/{current_order[1]}'
            if current_order[4] == 1:
                discord_id = 'Anonymous'
            elif current_order[4] in (2, 3):
                res = db.query('users', ['display_name'], {'rowid': int(current_order[5])})
                if res is not None:
                    discord_id = f'`{res[1]}`'
                else:
                    discord_id = 'null'
        
        f = open('globals/webhook.txt')
        discord_webhook_url = f.read()
        f.close()

        special_effects = ""
        if "Yearly" in sniper_translation[request_data["snipe"]]:
            special_effects = '**'
        
        f = open('globals/claimping.txt', 'r')
        claim_ping = f.read()
        f.close()

        try:
            httpx.post(discord_webhook_url, json={
                'content': f'{emoji} Claimed {special_effects}`{sniper_translation[request_data["snipe"]]}`{special_effects} for {discord_id} `(#{order_id}) ({progress})` in `{request_data["time"]}`. <@&{claim_ping}>'
            })
        except:
            pass
        
    except:
        app.logger.warn(f'failed to send discord webhook: {traceback.format_exc()}')


@app.route('/api/v1/sniper', methods=['POST'])
@limiter.limit("1 per 5 seconds", deduct_when=lambda response: response.status_code == 401)
def api_sniper():
    auth_id = request.headers.get('Authorization')
    instance_id = request.headers.get('X-Instance-ID')
    if auth_id != config.sniper_auth:
        return utils.j({'error': True, 'message': 'Unauthorized.', 'token': ''}), 401
    
    f = open('globals/defaulttoken.txt')
    default_token = f.read()
    f.close()
    
    try:
        request_data = {
            'type': request.json['type']
        }
    except:
        return utils.j({'error': True, 'message': 'Data Error.', 'token': ''}), 400
    
    hit_msg = []

    db = database.Connection(config.db_name)
    if request_data['type'] == 1: # snipe hit
        try:
            request_data["snipe"] = request.json['snipe']
            request_data["token"] = request.json['token']
        except:
            return utils.j({'error': True, 'message': 'Data Error.', 'token': ''}), 400
        
        try:
            request_data["time"] = request.json['time']
        except:
            request_data["time"] = "xxx.xxxms"

        with proccess_hit_lock:
            process_hit(db, instance_id, request_data)
    
    elif request_data['type'] == 0: # 5s interval ping
        try:
            request_data["alts"] = request.json['alts']
            request_data["servers"] = request.json['servers']
        except:
            return utils.j({'error': True, 'message': 'Data Error.', 'token': ''}), 400
        
        global instances, alts, servers
        instances[instance_id] = {'alts': request_data['alts'], 'servers': request_data['servers'], 'last_seen': int(time.time())}
        tmp_alts,tmp_servers = 0,0
        for inst_data in instances.values():
            tmp_alts += int(inst_data["alts"])
            tmp_servers += int(inst_data["servers"])
        alts = tmp_alts
        servers = tmp_servers
    
    elif request_data['type'] == 2: # vps rate limited, try on this server...
        try:
            request_data["code"] = request.json['code']
            request_data['time'] = int(request.json['time']) / 1000
        except:
            return utils.j({'error': True, 'message': 'Data Error.', 'token': ''}), 400
        
        token_order = db.query2('SELECT token FROM orders WHERE status != ?', ['2'], False)
        if token_order:
            recent_token = token_order[0][0]
        else:
            recent_token = default_token

        curl = pycurl.Curl()
        curl.setopt(pycurl.POST, 1)

        curl.setopt(pycurl.URL, "https://discord.com/api/v9/entitlements/gift-codes/" + request_data["code"] + "/redeem")
        curl.setopt(pycurl.POSTFIELDS, '{"channel_id": null, "payment_source_id": null}')
        curl.setopt(pycurl.HTTPHEADER, ['Content-Type: application/json', 'Authorization: ' + recent_token, 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'])
        curl.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_2_0)
        buffer = io.BytesIO()
        curl.setopt(pycurl.WRITEFUNCTION, buffer.write)
        curl.perform()
        end_time = time.time()

        response_code = curl.getinfo(pycurl.RESPONSE_CODE)
        response_body = buffer.getvalue()
        resjson = json.loads(response_body)
        if response_code == 200:
            app.logger.info('self snipe from rate limit')
            request_data_for_func = {
                'snipe': resjson['subscription_plan']['name'],
                'token': recent_token,
                'time': end_time - request_data['time'],
                'type': 1
            }
            process_hit(db, instance_id, request_data_for_func)
            hit_msg = ["1", resjson['subscription_plan']['name'], str(end_time - request_data['time'])]
        
        else:
            hit_msg = ["0", resjson.get('message', 'JSON Fail'), str(end_time - request_data['time'])]
        
        curl.close()
            
    
    queue = db.query2('SELECT token, quantity, claim_data FROM orders WHERE status != ?', ['2'], False)
    if queue:
        recent_token = queue[0][0]
    else:
        recent_token = default_token
    
    queue_tokens = []
    queue_amount = []
    for order in queue:
        queue_tokens.append(order[0])
        queue_amount.append(order[1] - len(json.loads(order[2])))

    queue_tokens.append(default_token)
    queue_amount.append(-999) # to let sniper know not to move this token

    db.close()

    return utils.j({
        "error": False,
        "token": recent_token, # legacy
        'message': '',
        'queue_tokens': queue_tokens,
        'queue_amount': queue_amount,
        'hit_msg': hit_msg # successful hit, reason/nitrotype, snipe_time
    }), 200