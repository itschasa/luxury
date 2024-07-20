from main import app, limiter, sock
import utils, config
import database

from flask import request
import time

time_to_reply = 0

global_socks = {}

def time_to_reply_thread():
    global time_to_reply
    while True:
        db = database.Connection(config.db_name)
        tickets = db.query2('SELECT first_reply, creation_time FROM tickets WHERE first_reply != ? ORDER BY rowid DESC LIMIT 5', ['0'], False)
        db.close()
        total_time = 0
        for ticket in tickets:
            total_time += ticket[0] - ticket[1]
        if total_time > 0:
            time_to_reply = int(total_time / len(ticket))

        time.sleep(30)


def ticket_data(user_id, role):
    if role == 'User':
        where_condition = {'author': user_id}
    else:
        where_condition = {}
    
    db = database.Connection(config.db_name)
    tickets = db.query('tickets', ['open', 'creation_time'], where_condition, False)
    tickets_data = []
    for ticket in tickets:
        seen_check = db.query2('SELECT rowid, seen_by FROM ticket_msgs WHERE ticket = ? ORDER BY rowid DESC;', [ticket[0]], True)
        if seen_check is None:
            seen = True
        else:
            if f'-{user_id}-' in seen_check[1]:
                seen = True
            else:
                seen = False
        tickets_data.append({
            'id': utils.clean_id(ticket[0]),
            'seen': seen,
            'creation_time': ticket[2],
            'open': True if ticket[1] == 1 else False
        }) 
    db.close()

    tickets_data.reverse() # highest id first
    return tickets_data


@sock.route('/api/v1/users/@me/tickets/websocket')
@limiter.limit("1 per 2 seconds")
def ws_ticket(ws):
    print('> websock connection')
    
    global global_socks
    
    user_id = utils.authenticate(request)
    if user_id == False:
        ws.send(utils.j({'op': 'close', 'endpoint': 'login'}))
        ws.close(); return
    
    if request.cookies.get('ssid').startswith('api_'):
        ws.send(utils.j({'op': 'close', 'reason': 'api not allowed, fuck off'}))
        ws.close(); return
    
    ticket_id = request.args.get('id')
    if ticket_id is None:
        ws.send(utils.j({'op': 'close', 'endpoint': ''}))
        ws.close(); return
    ticket_id_int = int(ticket_id)

    db = database.Connection(config.db_name)
    search_ticket = db.query('tickets', ['author', 'open'], {'rowid': ticket_id_int})
    if search_ticket is None:
        ws.send(utils.j({'op': 'close', 'endpoint': ''}))
        ws.close(); return

    # perms check
    role_check = db.query('users', ['role'], {'rowid': user_id})
    if search_ticket[1] != user_id:
        if role_check == None or role_check[1] == 'User':
            ws.send(utils.j({'op': 'close', 'endpoint': ''}))
            ws.close(); return
    
    ticket_messages = db.query('ticket_msgs', ['content', 'author', 'seen_by', 'time'], {'ticket': ticket_id_int}, False)
    message_list = []
    unseen_point = None
    users_found = {0: 'System'}
    for message in ticket_messages:
        if f'-{user_id}-' not in message[3] and unseen_point is None:
            unseen_point = message[0]
            message_list.append({
                'type': 1
            })
        
        message_author = users_found.get(message[2])
        if message_author is None:
            message_author = db.query('users', ['display_name'], {'rowid': message[2]})[1]
            users_found[message[2]] = message_author
        
        message_list.append({
            'type': 0,
            'time': message[4],
            'user': {
                'display_name': message_author,
                'id': message[2]
            },
            'content': message[1]
        })
    
    # update seen_by
    db.command("UPDATE ticket_msgs SET seen_by = seen_by || ? WHERE ticket = ? AND rowid >= ? AND seen_by NOT LIKE ?", [f'-{user_id}-', ticket_id_int, unseen_point, f'%-{user_id}-%'])
    db.close()

    if role_check[1] != 'User':
        ticket_open = True
    elif search_ticket[2] == 1:
        ticket_open = True
    else:
        ticket_open = False

    ws.send(utils.j({
        'op': 'start',
        'data': message_list,
        'open': ticket_open
    }))

    sock_id = utils.rand_chars(5)

    if global_socks.get(ticket_id_int) is None:
        global_socks[ticket_id_int] = {user_id: {'ws': ws, 'id': sock_id}}
    elif global_socks[ticket_id_int].get(user_id) is None:
        global_socks[ticket_id_int][user_id] = {'ws': ws, 'id': sock_id}
    else:
        global_socks[ticket_id_int][user_id]['ws'] = ws
        global_socks[ticket_id_int][user_id]['id'] = sock_id

    while True:
        try:
            recv_data = ws.receive(timeout=10) # online check
        except:
            try: ws.close()
            except: pass
            
            if global_socks[ticket_id_int][user_id]['id'] == sock_id:
                del global_socks[ticket_id_int][user_id]
            return
        
        else:
            if recv_data is None or global_socks[ticket_id_int][user_id]['id'] != sock_id:
                ws.send(utils.j({'op': 'close', 'endpoint': ''}))
                ws.close(); return


@app.route('/api/v1/users/@me/tickets/<ticket_id>/message', methods=['POST'])
@limiter.limit("1 per 2 seconds")
@limiter.limit("10 per 1 minute", deduct_when=lambda response: response.status_code == 200)
def api_send_message(ticket_id):
    global global_socks
    
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401
    
    if request.cookies.get('ssid').startswith('api_'):
        return utils.j({'error': True, 'message': "API Keys Forbidden."}), 403
        
    try:
        request_data = {
            'content': utils.xss_safe(request.json['content'])
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if len(request_data['content']) < 1:
        return utils.j({'error': True, 'message': "Message too short."}), 400

    if len(request_data['content']) > 2000:
        return utils.j({'error': True, 'message': "Message can't be larger than 2000 characters."}), 400
    
    ticket_id_int = int(ticket_id)

    db = database.Connection(config.db_name)
    search_ticket = db.query('tickets', ['author', 'open', 'first_reply'], {'rowid': ticket_id_int})
    if search_ticket is None:
        db.close()
        return utils.j({'error': True, 'message': "Unknown Ticket."}), 400

    # perms check
    role_check = db.query('users', ['role', 'display_name'], {'rowid': user_id})
    if search_ticket[1] != user_id:
        if role_check == None or role_check[1] == 'User':
            db.close()
            return utils.j({'error': True, 'message': "Forbidden."}), 403
    
    if search_ticket[2] == 0 and role_check[1] == 'User':
        db.close()
        return utils.j({'error': True, 'message': "Ticket is closed."}), 400
    
    additional_data = None
    if role_check[1] != 'User':
        if request_data['content'] == '/close':
            db.edit('tickets', {'open': 0}, {'rowid': ticket_id_int})
            additional_data = utils.j({'op': 'update', 'data': {
                'open': False
            }})
            request_data['content'] = 'The ticket has been **closed**.'
        elif request_data['content'] == '/open':
            db.edit('tickets', {'open': 1}, {'rowid': ticket_id_int})
            additional_data = utils.j({'op': 'update', 'data': {
                'open': True
            }})
            request_data['content'] = 'The ticket has been **reopened**.'
    
    seen_by = ''
    time_stamp = int(time.time())
    
    if global_socks.get(ticket_id_int) is not None:
        data_to_sent = utils.j({'op': 'message', 'data': {
            'type': 0,
            'time': time_stamp,
            'user': {
                'display_name': role_check[2],
                'id': user_id
            },
            'content': request_data['content']
        }})
        for user, ws in global_socks[ticket_id_int].copy().items():
            try:
                ws['ws'].send(data_to_sent)
                if additional_data is not None:
                    ws['ws'].send(additional_data)
            except:
                try: del global_socks[ticket_id_int][user]
                except: pass
            else: seen_by += f'-{user}-'

    if search_ticket[3] == 0 and search_ticket[1] != user_id:
        db.edit('tickets', {'first_reply': time_stamp}, {'rowid': ticket_id_int})

    db.insert('ticket_msgs', [request_data['content'], user_id, int(ticket_id), seen_by, time_stamp])
    db.close()
    
    return utils.j({'error': False}), 200



@app.route('/api/v1/users/<url_user>/tickets', methods=['POST'])
@limiter.limit("4 per 7 seconds", deduct_when=lambda response: response.status_code == 200)
def api_create_ticket(url_user):
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
        
    try:
        request_data = {
            'title': utils.xss_safe(request.json['title']).replace('*', ''),
            'description': utils.xss_safe(request.json['description']),
            'captcha': request.json['token']
        }
    except:
        db.close()
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if len(request_data['title']) < 10:
        db.close()
        return utils.j({'error': True, 'message': "Title too short."}), 400 
    
    if len(request_data['description']) < 25:
        db.close()
        return utils.j({'error': True, 'message': "Description too short."}), 400 

    if utils.turnstile(request_data['captcha'], request.access_route[0]) == False:
        db.close()
        return utils.j({'error': True, 'message': "Captcha Invalid. Please try again."}), 400

    open_tickets = len(db.query('tickets', ['author'], {'open': '1', 'author': user_id}, False))
    if open_tickets > config.max_open_tickets:
        db.close()
        return utils.j({'error': True, 'message': "Too many open tickets."}), 403
    
    time_stamp = int(time.time())
    db.insert('tickets', [user_id, time_stamp, '1', '0'])
    ticket_id = db.query('tickets', ['author'], {'creation_time': time_stamp, 'author': user_id})[0]
    message_content = f"\n**Title:** {request_data['title']}\n**Description:** {request_data['description']}"
    db.insert('ticket_msgs', [message_content, user_id, int(ticket_id), '', time_stamp])
    db.insert('ticket_msgs', ["Your Ticket has been sent! Please wait for our response. You can see the average time until reply on the dashboard.", 0, int(ticket_id), '', time_stamp])
    db.close()
    ticket_id = utils.clean_id(ticket_id)

    utils.admin_webhook(f'New Ticket `#{ticket_id}` `{request_data["title"]}` | @everyone\n```\n{request_data["description"]}```')
    
    return utils.j({'error': False, 'message': f"Created Ticket #{ticket_id}. Redirecting...", 'id': ticket_id}), 200


@app.route('/api/v1/users/<url_user>/tickets', methods=['GET'])
@limiter.limit("4 per 7 seconds", deduct_when=lambda response: response.status_code == 200)
def api_list_tickets(url_user):
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

    user_role = db.query('users', ['role'], {'rowid': user_id})
    db.close()
    if user_role is None:
        return utils.j({'error': True, 'message': "Unknown User."}), 400
    
    return utils.j(ticket_data(user_id, user_role[1])), 200