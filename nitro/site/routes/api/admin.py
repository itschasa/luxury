from main import app, limiter, orders, credits, tickets, sniper, queue
import utils, config, database

import time, json, httpx
from flask import request, make_response

last_ping = 0

def status_thread():
    global last_ping
    while True:
        f = open('globals/statuswebhook.txt', 'r')
        webhook_url = f.read()
        f.close()

        f = open('globals/statusid.txt', 'r')
        webhook_msg_id = f.read()
        f.close()

        offline_vps = []
        emojis = ("<a:online:1146457523960959108>", "<a:offline:1146457528339808426>")
        description = ""
        current_time = int(time.time())
        for instance_id in sorted(list(sniper.instances.keys()), key=int):
            instance_data = sniper.instances[instance_id]
            # {'alts': request_data['alts'], 'servers': request_data['servers'], 'last_seen': int(time.time())}
            if instance_data['last_seen'] < current_time - 45:
                index = 1
                offline_vps.append(instance_id)
            else:
                index = 0
                
            description += f"> {emojis[index]}⠀`Instance {instance_id}` - `{int(instance_data['servers']):,} Guilds / {int(instance_data['alts']):,} Alts`\n"

        try: httpx.patch(webhook_url+f"/messages/{webhook_msg_id}", json={
            "content": "",
            "embeds": [
                {
                    "description": f"If any are offline, then snipes may be slower than usual.\n\n{description}",
                    "color": 8077755,
                    "author": {
                        "name": "Sniper Instances"
                    }
                }
            ]
        })
        except: pass

        f = open('globals/adminwebhook.txt')
        discord_webhook_url = f.read()
        f.close()

        if len(offline_vps) > 0:
            if last_ping < current_time - 900:
                try: httpx.post(discord_webhook_url, json={
                    "content": f"VPS OFFLINE // {','.join(offline_vps)} @everyone"
                })
                except: pass
                else: last_ping = current_time
        
        time.sleep(20)


@app.route('/api/v1/admin', methods=['POST'])
@limiter.limit("1 per 5 seconds", deduct_when=lambda response: response.status_code == 401)
def api_admin():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    db = database.Connection(config.db_name)
    admin_check = db.query('users', ['role', 'display_name'], {'rowid': user_id})
    if not (admin_check is not None and admin_check[1] != 'User'):
        db.close()
        return utils.j({'error': True, 'message': "Forbidden."}), 403

    try:
        request_data = {
            'command': str(request.json['command'])
        }
    except:
        db.close()
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    current_time = int(time.time())
    return_message = {'name': 'System'}
    set_cookie = None
    extra_data = {}

    help_data = {
        'lookup': '/lookup [query] - Find a user based on IP, username, or email.',
        'credits': '/credits [user id] [quantity] [reason] - Add/remove credits from a user.',
        'login': '/login [user id] - Login to a different account, from user id.',
        'user': '/user [user id] - Display orders, info, tickets, and credits history of that user.',
        'sniper': '/sniper - Displays details about sniper instances.',
        'credit_history': '/credit_history [+/-/b] [user id/0] - Shows history of credits, using filters.',
        'emailfix': "/emailfix [user id] [new email] - Changes and verifies a user's email.",
        'setwebhook': "/setwebhook [url] - Changes Discord Webhook to notify about hits.",
        'setadminwebhook': "/setadminwebhook [url] - Changes Discord Webhook to notify about new tickets, etc.",
        'setclaimping': "/setclaimping [roleid] - Updates Role ID for Claim Ping for hits",
        'updatestatuswebhook': "/updatestatuswebhook [url] - Sends a discord message on the webhook, and uses that as the message to edit.",
        'updatequeuewebhook': "/updatequeuewebhook [url] - Sends a discord message on the webhook, and uses that as the message to edit.",
        'setorderwebhook': "/setorderwebhook [url] - Changes Discord Webhook to notify about new orders on sellix.",
        'setfeedbackwebhook': "/setfeedbackwebhook [url] - Changes Discord Webhook to notify about new feedback on sellix.",
        'defaulttoken': "/defaulttoken [token] - Changes Discord Token to use when no one is in queue.",
        'setnews': "/setnews [html] - Alert shown on Home Page; set to null to clear.",
        'paypalpaid': "/paypalpaid [transaction id] - Set a PayPal Payment as already claimed (payments that aren't for claims).",
        'delorder': "/delorder [order id] [refund (y/n)] [reason] - Delete an order from the queue (will not give Basic refunds).",
        'setorderpos': "/setorderpos [order id] [position] - Changes the queue order. Position starts at 1.",
        'discordterm': '/discordterm - Explains what to do when discord terms.',
        "raworder": '/raworder [order id] - Returns all data about an order.',
        "inflation": '/inflation [credit value in usd] - Show data about the credit economy.'
    }
    if request_data['command'].startswith('/discordterm'):
        return_message['content'] = "\n1. /setwebhook [webhook url for claims]\n2. /setadminwebhook [webhook url for tickets]\n3. /updatequeuewebhook [webhook url for queue]\n4. /setorderwebhook [webhook url for orders]\n5. /setfeedbackwebhook [webhook url for feedback]\n6. /updatestatuswebhook [webhook url for #status]\n7. /setclaimping [roleid for claim ping]\n8. /setnews News: New Discord Server: https://discord.gg/1234567"
    
    elif request_data['command'].startswith('/delorder'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'orderid': int(command_args[1]),
                'refund': True if command_args[2].lower() == 'y' else False,
                'reason': ''.join(x + ' ' for x in command_args[3:])[:-1]
            }
        except:
            return_message['content'] = help_data["delorder"]
        else:
            order = db.query2('SELECT referral, quantity, claim_data, token, user, status FROM orders WHERE referral = ?', [command_data['orderid']], True)
            if order is None:
                return_message['content'] = 'Invalid Order ID.'
            
            else:
                refund_amount = order[1] - len(json.loads(order[2])) if command_data['refund'] else 0
                
                balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [order[4]], True)
                if balance is None: balance = 0
                else: balance = balance[0]
                
                db.insert('credits', [refund_amount, order[4], f'#{utils.clean_id(order[0])}: {command_data["reason"]}', balance + refund_amount, int(time.time())])
                db.edit('orders', {'quantity': len(json.loads(order[2])), 'status': 2}, {'referral': order[0]})

                return_message['content'] = f"Order has been removed! User's new balance is {balance}. (refund={command_data['refund']})"
    
    elif request_data['command'].startswith('/setorderpos'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'orderid': int(command_args[1]),
                'position': int(command_args[2])
            }
        except:
            return_message['content'] = f'{help_data["setorderpos"]}'
        else:
            user_order = db.query2('SELECT rowid, user, quantity, timestamp, status, claim_data, referral, token, anonymous FROM orders WHERE referral = ?', [command_data['orderid']], True)
            if user_order is None:
                return_message['content'] = 'Invalid Order ID.'
            else:
                if user_order[4] == '2':
                    return_message['content'] = 'Order has already been completed.'
                else:
                    new_orders = []
                    _orders = db.query2('SELECT rowid, user, quantity, timestamp, status, claim_data, referral, token, anonymous FROM orders WHERE status = ? OR status = ?', ['1', '0'], False)
                    order_delete_str = ""
                    order_ids = []
                    queue_order = ""
                    for order in _orders:
                        order_delete_str += "rowid = ? OR "
                        order_ids.append(order[0])
                        queue_order += f"\n-{'>' if order[6] == str(command_data['orderid']) else ''} #{utils.clean_id(order[6])}"
                        
                        if order[6] != str(command_data['orderid']):
                            if len(new_orders) + 1 == command_data['position']:
                                new_orders.append(list(user_order[1:]))
                            new_orders.append(list(order[1:]))

                    if list(user_order[1:]) not in new_orders:
                        new_orders.append(list(user_order[1:]))

                    order_delete_str = order_delete_str[:-4]
                    db.delete('orders', {}, whereOverRide=order_delete_str, valuesOverRide=order_ids)

                    queue_order_new = ""
                    for order in new_orders:
                        if new_orders.index(order) == 0:
                            order[3] = '1'
                        else:
                            order[3] = '0'
                        queue_order_new += f"\n-{'>' if order[5] == str(command_data['orderid']) else ''} #{utils.clean_id(order[5])}"
                        db.insert("orders", order)
                    
                    return_message['content'] = f'Order is now at position {command_args[2]}.\n**Old Order:**{queue_order}\n\n**New Order:**{queue_order_new}'

    elif request_data['command'].startswith('/credits'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user': int(command_args[1]),
                'quantity': int(command_args[2]),
                'reason': ''.join(x + ' ' for x in command_args[3:])[:-1]
            }
        except:
            return_message['content'] = f'{help_data["credits"]}\n**Note:** [quantity] can be negative to take credits away.'
        else:
            requested_user = db.query('users', ['display_name'], {'rowid': command_data['user']})
            if requested_user is None:
                return_message['content'] = "Couldn't find user with that ID."
            else:
                balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [command_data['user']], True)
                if balance is None: balance = 0
                else: balance = balance[0]
                db.insert('credits', [str(command_data['quantity']), command_data['user'], command_data['reason'], balance+command_data['quantity'], current_time])
                if 'paypal' in command_data['reason'].lower():
                    utils.send_order_webhook(f"💸 `{command_data['quantity']}x` [`Nitro Claim`](https://dash.luxurynitro.com/purchase) has been bought via `PayPal (manual)`!")
                
                return_message['content'] = f"**Done!** {requested_user[1]}'s new balance is {balance+command_data['quantity']}"
    
    elif request_data['command'].startswith('/lookup'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'search': command_args[1]
            }
        except:
            return_message['content'] = help_data["lookup"]
        else:
            user_data = db.query2('SELECT rowid, username, display_name, email, email_verified, role, ips, time FROM users WHERE username LIKE ? OR display_name LIKE ? OR ips LIKE ? OR email LIKE ?', [f'%{command_data["search"]}%', f'%{command_data["search"]}%', f'%{command_data["search"]}%', f'%{command_data["search"]}%'], False)
            if user_data is None:
                return_message['content'] = 'No users found.'
            else:
                return_message['content'] = f"**Found {len(user_data)} user{'s' if len(user_data) > 1 else ''}.**"
                for user in user_data:
                    return_message['content'] += f"""\n--- **{user[2]}** ---
**Username**: {user[1]} ({user[2]})
**User ID**: {user[0]}
**Email**: {user[3]}
**Verified?** {'yes' if user[4] == 'True' else 'no'}
**Role**: {user[5]}
**IPs**: {user[6]}
**Creation Timestamp**: {user[7]}\n"""

    elif request_data['command'].startswith('/login'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user': int(command_args[1])
            }
        except:
            return_message['content'] = help_data["login"]
        else:
            user_data = db.query2('SELECT username FROM users WHERE rowid = ?', [command_data['user']], True)
            if user_data is None:
                return_message['content'] = 'No users found.'
            else:
                cookie = utils.rand_chars(64)
                db.insert('cookies', [
                    cookie,
                    command_data['user'],
                    int(time.time()),
                    request.headers.get('User-Agent'),
                    request.access_route[0]
                ])
            
            set_cookie = cookie
            return_message['content'] = 'Cookie set! Refresh your page.'

    elif request_data['command'].startswith('/user'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user': int(command_args[1])
            }
        except:
            return_message['content'] = help_data["user"]
        else:
            user = db.query2('SELECT rowid, username, display_name, email, email_verified, role, ips, time FROM users WHERE rowid = ?', [command_data['user']], True)
            if user is None:
                return_message['content'] = 'No users found.'
            else:
                ticket_data = tickets.ticket_data(user[0], user[5])
                return_message['content'] = f"""\n--- **{user[2]}** ---
**Username**: {user[1]} ({user[2]})
**User ID**: {user[0]}
**Email**: {user[3]}
**Verified?** {'yes' if user[4] == 'True' else 'no'}
**Role**: {user[5]}
**IPs**: {user[6]}
**Creation Timestamp**: {user[7]}
**{len(ticket_data)} tickets**:"""
                for ticket in ticket_data:
                    return_message['content'] += f"\n- #{ticket['id']}{' ' if ticket['seen'] else ' (unread)'}{' (open)' if ticket['open'] else ' (closed)'}"
                extra_data['orders'] = orders.order_data(command_data['user'])
                extra_data['credits'] = credits.credit_data(command_data['user'])

    elif request_data['command'].startswith('/raworder'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'orderid': int(command_args[1])
            }
        except:
            return_message['content'] = help_data["raworder"]
        else:
            order = db.query2('SELECT referral, user, quantity, timestamp, status, claim_data, token, anonymous FROM orders WHERE referral = ?', [command_data['orderid']], True)
            if order is None:
                return_message['content'] = 'Order not found.'
            else:
                return_message['content'] = f"ID={order[0]}\nUser={order[1]}\nQuantity={order[2]}\nTimestamp={order[3]}\nStatus={order[4]}\nClaimData={json.dumps(json.loads(order[5]), indent=4)}\nToken={order[6]}\nAnonymous={order[7]}"

    elif request_data['command'].startswith('/sniper'):
        return_message['content'] = "\n"
        total_alts, total_servers = 0, 0
        for inst_id, inst_data in sniper.instances.items():
            # {'alts': request_data['alts'], 'servers': request_data['servers'], 'last_seen': int(time.time())}
            total_alts += int(inst_data["alts"])
            total_servers += int(inst_data["servers"])
            return_message['content'] += f'**{inst_id}**: Seen {int(time.time()) - inst_data["last_seen"]}s ago, {inst_data["alts"]} alts, {inst_data["servers"]} servers.\n'
        
        return_message['content'] += f'**{total_alts} total alts** | **{total_servers} total servers**'

    elif request_data['command'].startswith('/emailfix'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'user': int(command_args[1]),
                'email': command_args[2]
            }
        except:
            return_message['content'] = help_data["emailfix"]
        else:
            user = db.query2('SELECT rowid, username, display_name, email, email_verified, role, ips, time FROM users WHERE rowid = ?', [command_data['user']], True)
            if user is None:
                return_message['content'] = 'No users found.'
            else:
                db.edit('users', {'email': command_data['email'], 'email_verified': 'True'}, {'rowid': command_data['user']})
                return_message['content'] = 'Email replaced.'

    elif request_data['command'].startswith('/credit_history'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'filter': command_args[1],
                'user': int(command_args[2])
            }
        except:
            return_message['content'] = help_data["credit_history"]
        else:
            search = None
            if command_data['filter'] == 'b' and command_data['user'] == 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits', [], False)
            if command_data['filter'] == 'b' and command_data['user'] != 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits WHERE user = ?', [command_data['user']], False)
            elif command_data['filter'] == '+' and command_data['user'] == 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits WHERE change NOT LIKE ?', [f'%-%'], False)
            elif command_data['filter'] == '+' and command_data['user'] != 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits WHERE change NOT LIKE ? AND user = ?', [f'%-%', command_data['user']], False)
            elif command_data['filter'] == '-' and command_data['user'] == 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits WHERE change LIKE ?', [f'%-%'], False)
            elif command_data['filter'] == '-' and command_data['user'] != 0:
                search = db.query2(f'SELECT rowid, change, user, reason, balance, time FROM credits WHERE change LIKE ? AND user = ?', [f'%-%', command_data['user']], False)
            
            if search is None:
                return_message['content'] = help_data["credit_history"]
            else:
                return_message['content'] = f"""**Found {len(search)} results:**\nID | Change | User | Reason | Balance | Timestamp"""
                for result in search:
                    return_message['content'] += f"\n#{utils.clean_id(result[0])} | {result[1]} | {result[2]} | {result[3]} | {result[4]} | {result[5]}"
    
    elif request_data['command'].startswith('/setwebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["setwebhook"]
        else:
            f = open('globals/webhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            return_message['content'] = 'Updated!'

    elif request_data['command'].startswith('/setadminwebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["setadminwebhook"]
        else:
            f = open('globals/adminwebhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            return_message['content'] = 'Updated!'

    elif request_data['command'].startswith('/setclaimping'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'id': command_args[1]
            }
        except:
            return_message['content'] = help_data["setclaimping"]
        else:
            f = open('globals/claimping.txt', 'w')
            f.write(command_data['id'])
            f.close()
            return_message['content'] = 'Updated!'
    
    elif request_data['command'].startswith('/setorderwebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["setorderwebhook"]
        else:
            f = open('globals/orderwebhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            return_message['content'] = 'Updated!'
    
    elif request_data['command'].startswith('/setfeedbackwebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["setfeedbackwebhook"]
        else:
            f = open('globals/feedbackwebhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            return_message['content'] = 'Updated!'

    elif request_data['command'].startswith('/updatequeuewebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["updatequeuewebhook"]
        else:
            f = open('globals/queuewebhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            
            webhook_msg_id = httpx.post(command_data['url']+"?wait=true", json={'content': 'test'}).json()['id']
            
            f = open('globals/queueid.txt', 'w')
            f.write(webhook_msg_id)
            f.close()
            
            return_message['content'] = 'Message sent, and queue ID updated!'
    
    elif request_data['command'].startswith('/updatestatuswebhook'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'url': command_args[1]
            }
        except:
            return_message['content'] = help_data["updatestatuswebhook"]
        else:
            f = open('globals/statuswebhook.txt', 'w')
            f.write(command_data['url'])
            f.close()
            
            webhook_msg_id = httpx.post(command_data['url']+"?wait=true", json={'content': 'test'}).json()['id']
            
            f = open('globals/statusid.txt', 'w')
            f.write(webhook_msg_id)
            f.close()
            
            return_message['content'] = 'Message sent, and queue ID updated!'
    
    elif request_data['command'].startswith('/defaulttoken'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'token': command_args[1]
            }
        except:
            return_message['content'] = help_data["defaulttoken"]
        else:
            f = open('globals/defaulttoken.txt', 'w')
            f.write(command_data['token'])
            f.close()
            return_message['content'] = 'Updated!'
    
    elif request_data['command'].startswith('/setnews'):
        try:
            if '/setnews ' not in request_data['command']:
                raise Exception
            command_data = {
                'content': request_data['command'].replace('/setnews ', '')
            }
        except:
            return_message['content'] = help_data["setnews"]
        else:
            f = open('globals/news.txt', 'w')
            f.write(command_data['content'])
            f.close()
            return_message['content'] = 'Updated!'
    
    elif request_data['command'].startswith('/paypalpaid'):
        try:
            command_args = request_data['command'].split(' ')
            command_data = {
                'id': command_args[1]
            }
        except:
            return_message['content'] = help_data["paypalpaid"]
        else:
            db.insert('paypal', [command_data['id'], 'claimed'])
            return_message['content'] = 'Set payment as claimed!'
    
    elif request_data['command'].startswith("/inflation"):
        try:
            command_args = request_data['command'].split(' ')
            credit_value = float(command_args[1])
        except:
            return_message['content'] = help_data["inflation"]
        else:
            res = db.query('credits', ['balance', 'user'], {}, False)
            credits_dict = {}
            for cred in res:
                credits_dict[cred[2]] = cred[1]
            total_credits = sum(list(credits_dict.values()))
            top_credit_holders = sorted(credits_dict.items(), key= lambda pair: pair[1], reverse=True)[:5]
            return_message['content'] = f'\n**Economy:**\n- Market Cap: ${total_credits * credit_value} ({total_credits} creds)\n- Top Holders (user=credits=value): {" / ".join(f"{x[0]}={x[1]}={int(x[1] * credit_value * 100) / 100}" for x in top_credit_holders)}\n- Queue: {queue.global_queue_total} (worth ${int(queue.global_queue_total*credit_value*100)/100})\n- Credit Burn Rate (day): {int((86400 / queue.global_eta_per_gift)*100)/100} (${(int((86400 / queue.global_eta_per_gift)*100)/100)*credit_value})\n- Credit Burn Rate (week): {int((604800 / queue.global_eta_per_gift)*100)/100} (${(int((604800 / queue.global_eta_per_gift)*100)/100)*credit_value})'

    elif request_data['command'].startswith('/help'):
        return_message['content'] = f"""**Help Menu:**"""
        for cmd in help_data.values():
            return_message['content'] += f'\n{cmd}'
    
    else:
        return_message['content'] = 'Unknown Command, type /help to view all commands.'

    db.close()
    return_message['time'] = int(time.time())
    res = make_response(utils.j({'messages': [{'time': current_time, 'name': admin_check[2], 'content': request_data['command']}, return_message], **extra_data}))
    if set_cookie is not None: res.set_cookie("ssid", value=set_cookie, max_age=config.cookie_timeout)
    return res, 200