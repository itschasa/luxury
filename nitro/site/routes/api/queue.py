from main import app, limiter
import database
import utils, config

import time
import json
import math
import httpx
import base64
from flask import request
import traceback

global_queue_data = {}
global_recent_data = []
global_queue_cleared = 0
global_eta_per_gift = 0
global_queue_total = 0
global_boost_percent = 0
global_classic_percent = 0
global_basic_percent = 0
global_claims_count = 0

boot_time = int(time.time())

def post_webhook(url, data):
    try:
        r = httpx.post(url+f"?wait=true", json={
            "content": None,
            "embeds": [data],
            "attachments": []
        })
    except:
        app.logger.warn(traceback.format_exc())
        return False
    else:
        if not str(r.status_code).startswith('2'):
            app.logger.warn(f'error from queue webhook: http:{r.status_code} {r.text}')
            return False
        else:
            return r.json()['id']

def edit_webhook(url, msg_id, data):
    try:
        r = httpx.patch(url+f"/messages/{msg_id}", json={
            "content": None,
            "embeds": [data],
            "attachments": []
        })
    except:
        app.logger.warn(traceback.format_exc())
        return False
    else:
        if not str(r.status_code).startswith('2'):
            app.logger.warn(f'error from queue webhook: http:{r.status_code} {r.text}')
            return False
        else:
            return True

def delete_webhook(url, msg_id):
    try:
        r = httpx.delete(url+f"/messages/{msg_id}")
    except:
        app.logger.warn(traceback.format_exc())
        return False
    else:
        if not str(r.status_code).startswith('2'):
            app.logger.warn(f'error from queue webhook: http:{r.status_code} {r.text}')
            return False
        else:
            return True

def queue_webhook_thread():
    webhook_msg_id = None
    time.sleep(2)
    while True:
        try:
            f = open('globals/queuewebhook.txt', 'r')
            webhook_url = f.read()
            f.close()

            f = open('globals/queueid.txt', 'r')
            webhook_msg_id = f.read().split(',')
            f.close()

            queue_copy = global_queue_data.copy().items()
            queue_eta_time = {}
            
            largest_gift_count_length = 0
            for _, order in queue_copy:
                if len(f"{order['quantity']}{order['received']}") > largest_gift_count_length:
                    largest_gift_count_length = len(str(order['quantity']) + str(order['received']))
                queue_eta_time[_] = utils.convertHMS(order['eta']['next'])
            
            largest_queue_length = 0
            for eta_str in queue_eta_time.values():
                if len(eta_str) > largest_queue_length:
                    largest_queue_length = len(eta_str)
            
            description = [f"🎁    `Queue Length: {global_queue_total}`\n⏰    `ETA Queue Cleared: {utils.convertHMS(global_queue_cleared)}`\n📡    `Last Updated: `<t:{int(time.time())}:R>\n"]
            db = database.Connection(config.db_name)
            for _, order in queue_copy:
                if order['user']['id'] == -1:
                    display_user = 'Anonymous'
                else:
                    if order['user']['mode'] in [2,3]:
                        display_user = '`'+order['user']['display_name']+'`'
                    else:
                        order_db = db.query2('SELECT referral, token FROM orders WHERE referral = ?', [int(order['id'])], True)
                        if order_db is not None:
                            display_user = '<@' + str(base64.b64decode(bytes(order_db[1].split('.')[0] + '==', encoding='utf-8')), encoding='utf-8') + '>'
                        else:
                            display_user = 'err!'
                
                new_data = f"\n{'<a:claiming:1116026143070507130>' if order['status'] == 1 else '<a:in_queue:1076604250534182922>'}    ` {order['received']}/{order['quantity']}{''.join(' ' for _ in range(largest_gift_count_length - len(str(order['quantity']) + str(order['received']))))} `  `{queue_eta_time[_]}{''.join(' ' for _ in range(largest_queue_length - len(queue_eta_time[_])))}`  {display_user}"
                if len(description[-1]) + len(new_data) > 4096:
                    description.append(new_data)
                else:
                    description[-1] += new_data
            db.close()

            embeds: list[dict] = []
            for desc in description:
                if description.index(desc) == 0:
                    embeds.append({
                        "title": "<a:nitroBoost:1093978431689072710>  Luxury Queue",
                        "description": f"{desc}",
                        "url": "https://dash.luxurynitro.com/",
                        "color": 11032831
                    })
                else:
                    embeds.append({
                        "description": f"{desc}",
                        "color": 11032831
                    })
            
            embeds[-1] = {
                **embeds[-1],
                "footer": {
                    "text": "Updates every 30 seconds.",
                    "icon_url": "https://cdn.discordapp.com/emojis/1114898869004804106.gif?size=96&quality=lossless"
                }
            }

            embed_ids = []
            for embed in embeds:
                try: int(webhook_msg_id[embeds.index(embed)])
                except:
                    res = post_webhook(webhook_url, embed)
                    if res:
                        embed_ids.append(res)
                else:
                    if edit_webhook(webhook_url, webhook_msg_id[embeds.index(embed)], embed):
                        embed_ids.append(webhook_msg_id[embeds.index(embed)])
                    else:
                        res = post_webhook(webhook_url, embed)
                        if res:
                            embed_ids.append(res)
            
            for msg_id in webhook_msg_id:
                if msg_id not in embed_ids:
                    delete_webhook(webhook_url, msg_id)
            
            f = open('globals/queueid.txt', 'w')
            f.write(','.join(embed_ids))
            f.close()

        except:
            app.logger.warn(traceback.format_exc())
        
        time.sleep(30)

def queue_data_thread():
    global global_eta_per_gift, global_queue_cleared, global_queue_data, global_recent_data, global_queue_total, global_boost_percent, global_basic_percent, global_classic_percent, global_claims_count
    while True:
        db = database.Connection(config.db_name)
        orders = db.query2('SELECT referral, user, quantity, timestamp, status, claim_data, anonymous FROM orders WHERE status != ?', ['2'], False)
        claims = db.query2('SELECT referral, user, quantity, timestamp, status, claim_data, anonymous FROM orders WHERE claim_data != ?', ['[]'], False)
        
        queue_data = {}

        current_time = int(time.time())
        total_claim_time = 0
        total_claims = 0
        last_claim_time = 0
        recent_claims = []

        claims_count = 0
        boost_count = 0
        basic_count = 0
        classic_count = 0


        recent_orders = []
        for order in claims[-500:]:
            for claim in json.loads(order[5]):
                recent_orders.append({**dict(claim), '_order': order})
        recent_orders = sorted(recent_orders, key = lambda claim: claim['time'])

        display_name_cache = {}

        for claim in recent_orders:
            if not display_name_cache.get(claim['_order'][1]):
                real_display_name = db.query('users', ['display_name'], {'rowid': claim['_order'][1]})[1]
                display_name_cache[claim['_order'][1]] = real_display_name
            else:
                real_display_name = display_name_cache.get(claim['_order'][1])
            
            if claim['_order'][6] == 1:
                display_name = 'Anonymous'
                user_id = -1
            else:
                display_name = real_display_name
                user_id = claim['_order'][1]
            
            if last_claim_time < claim['_order'][3]:
                last_claim_time = claim['_order'][3]
            
            claims_count += 1     
            total_claim_time += claim['time'] - last_claim_time
            total_claims += 1
            last_claim_time = claim['time']
            if 'Boost' in claim['type']: boost_count += 1
            last_claim_time = claim['time']
            if 'Basic' in claim['type']: basic_count += 1
            last_claim_time = claim['time']
            if 'Classic' in claim['type']: classic_count += 1                  
            recent_claims.append({
                'order': utils.clean_id(claim['_order'][0]),
                'time': claim['time'],
                'type': claim['type'],
                'user': {
                    'display_name': display_name,
                    'id': user_id
                }
            })

        global_boost_percent = int((boost_count / claims_count) * 10000) / 100
        global_basic_percent = int((basic_count / claims_count) * 10000) / 100
        global_classic_percent = int((classic_count / claims_count) * 10000) / 100


        for order in claims[:-500]:
            order_data = json.loads(order[5])
            claims_count += len(order_data)

        global_claims_count = claims_count
        
        recent_claims.reverse()
            
        if total_claim_time > 0:
            # 3rd quartile (kinda)
            global_eta_per_gift = int(total_claim_time / total_claims)
        else:
            # if no orders, then just assume last claim was on startup,
            # and have eta as 4.5 hours (just so i can see it working)
            global_eta_per_gift = 16200
            last_claim_time = boot_time

        total_quantity = 0
        counter = 0
        counter_for_next = 0
        time_since_last_claim = current_time - last_claim_time

        boost_chance_multiplier = math.ceil(100 / global_boost_percent)

        order_data_iters = {
            # "513": 1,
            # "514": 0
        }   # "orderid": highest int for iter, with that order id

        order_data_loop = {
           # "0_1_513": 1234,
           # "0_2_514": 1234,
           # "1_1_513": 1234
        }  # "iter_orderpos_orderid": time_til_move_to_back_of_queue

        received_dict = {
            # "orderid": 1
        }

        for order in orders:
            order_data = json.loads(order[5])
            quant_left = order[2] - len(order_data)
            received_dict[order[0]] = len(order_data)
            total_quantity += quant_left
            
            iters = quant_left // boost_chance_multiplier
            remain = quant_left % boost_chance_multiplier
            for x in range(iters):
                order_data_loop[f"{x}_{str(orders.index(order)).zfill(4)}_{order[0]}"] = boost_chance_multiplier * global_eta_per_gift
            
            if remain != 0:
                order_data_loop[f"{iters}_{str(orders.index(order)).zfill(4)}_{order[0]}"] = remain * global_eta_per_gift
            
            order_data_iters[order[0]] = iters if remain != 0 else iters - 1

        order_data_loop = dict(sorted(order_data_loop.items(), key = lambda x:x[0]))

        for order in orders:
            counter += 1
            if order[6] == 1:
                display_name = 'Anonymous'
                user_id = -1
            else:
                display_name = db.query('users', ['display_name'], {'rowid': order[1]})[1]
                user_id = order[1]
            
            completed_data = 0
            next_data = 0
            gifts_before_finished = 0
            found_first_iter = False
            for order_slug, order_time in order_data_loop.items():
                completed_data += order_time
                gifts_before_finished += order_time // global_eta_per_gift
                if not found_first_iter: next_data += order_time
                
                if not found_first_iter and order_slug == f"0_{str(orders.index(order)).zfill(4)}_{order[0]}":
                    found_first_iter = True
                
                if order_slug == f"{order_data_iters[order[0]]}_{str(orders.index(order)).zfill(4)}_{order[0]}":
                    break
            
            next_data = next_data - time_since_last_claim
            if next_data < 900*(counter+counter_for_next):
                next_data = 900*(counter+counter_for_next)

            completed_data = completed_data - time_since_last_claim
            if completed_data < 900*(gifts_before_finished-2): # yeah i have no idea why -2 works, but it just does, so leave it
                completed_data = 900*(gifts_before_finished-2)
                #counter += math.ceil(order[2]-received_dict[order[0]] / boost_chance_multiplier)
            
            counter_for_next += math.floor((order[2] - received_dict[order[0]]) / boost_chance_multiplier)

            queue_data[order[0]] = {
                'id': utils.clean_id(order[0]),
                'user': {
                    'display_name': display_name,
                    'id': user_id,
                    'mode': order[6]
                },
                'status': order[4], 
                'quantity': order[2],
                'received': received_dict[order[0]],
                'eta': {
                    'next': next_data,
                    'completed': completed_data
                }
            }

        db.close()

        queue_total = sum(list(order_data_loop.values())) - time_since_last_claim
        if queue_total < 900*total_quantity:
            queue_total = 900*total_quantity

        global_queue_data = queue_data.copy()
        global_recent_data = recent_claims.copy()
        global_queue_total = total_quantity
        global_queue_cleared = queue_total

        time.sleep(3)


@app.route('/api/v1/queue', methods=['GET'])
@limiter.limit("4 per 5 seconds", deduct_when=lambda response: response.status_code == 200)
def api_list_queue():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    return utils.j({
        "queue": list(global_queue_data.values()),
        "recent": global_recent_data,
        "eta_per_gift": global_eta_per_gift,
        "queue_cleared": global_queue_cleared,
        "queue_quantity": global_queue_total
    }), 200
    