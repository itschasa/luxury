# suck@chasa.wtf : 1aPB7R!z9d$I

from main import app, limiter
import utils, config, mail, hasher
import database

from flask import request
import json, flask, time, threading, httpx


@app.route('/api/v1/auth/login', methods=['POST'])
@limiter.limit("1 per 1 seconds")
def api_login():
    try:
        request_data = {
            'email': request.json['email'].lower(),
            'password': request.json['password'],
            'captcha': request.json['token'],
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if utils.turnstile(request_data['captcha'], request.access_route[0]) == False:
        return utils.j({'error': True, 'message': "Please try again."}), 400
    
    db = database.Connection(config.db_name)
    db_data = db.query('users', ['username', 'password', 'email_verified', 'ips', 'email'], {'email': request_data['email']})
    if db_data is None:
        db.close()
        return utils.j({'error': True, 'message': "Login or password is invalid."}), 400
    
    if hasher.check(request_data['password'], db_data[2]) == False:
        db.close()
        return utils.j({'error': True, 'message': "Login or password is invalid."}), 400

    if db_data[3] != 'True':
        db.close()
        return utils.j({'error': True, 'message': "Verify your email to continue."}), 400
    
    ip_data = json.loads(db_data[4])
    if request.access_route[0] not in ip_data:
        verify_token = utils.rand_chars(48)
        ip_data.append(f'{request.access_route[0]}/{verify_token}')
        db.edit('users', {'ips': json.dumps(ip_data)}, {'email': request_data['email']})
        mail.send(db_data[5], mail.verify_subject, mail.verify_content.format(request.access_route[0], request.access_route[0], verify_token))
        db.close()
        return utils.j({'error': True, 'message': "New Login Location. Check your email to continue."}), 400
    
    cookie = utils.rand_chars(64)
    db.insert('cookies', [
        cookie,
        db_data[0],
        int(time.time()),
        request.headers.get('User-Agent'),
        request.access_route[0]
    ])
    db.close()

    res = flask.make_response(utils.j({"error": False, "message": 'Redirecting...'}))
    res.set_cookie("ssid", value=cookie, max_age=config.cookie_timeout)
    return res, 200


@app.route('/api/v1/auth/register', methods=['POST'])
@limiter.limit("1 per 2 seconds")
@limiter.limit("1 per 90 seconds", deduct_when=lambda response: response.status_code == 200)
def api_register():
    try:
        request_data = {
            'username': request.json['username'],
            'email': request.json['email'].lower(),
            'password': request.json['password'],
            'confirm': request.json['confirm'],
            'captcha': request.json['token'],
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400

    if request_data['password'] != request_data['confirm']:
        return utils.j({'error': True, 'message': "Passwords don't match."}), 400

    username_check = utils.validate_string(request_data['username'], 'username', 3, 15)
    if username_check == False:
        return utils.j({'error': True, 'message': "Username needs to be 3-15 characters long."}), 400
    elif username_check is None:
        return utils.j({'error': True, 'message': "Username not allowed."}), 400
    
    password_check = utils.validate_string(request_data['password'], 'password', 8, 40)
    if password_check == False:
        return utils.j({'error': True, 'message': "Password needs to be 8-40 characters long."}), 400
    
    email_check = utils.validate_string(request_data['email'], 'email', None, 55)
    if email_check is None:
        return utils.j({'error': True, 'message': "Invalid Email. Please use a different one."}), 400
    
    if utils.turnstile(request_data['captcha'], request.access_route[0]) == False:
        return utils.j({'error': True, 'message': "Please try again."}), 400
    
    db = database.Connection(config.db_name)
    if db.query('users', ['email'], {'email': request_data['email']}) is not None:
        db.close()
        return utils.j({'error': True, 'message': "Email already in use."}), 400
    
    if db.query('users', ['username'], {'username': request_data['username'].lower()}) is not None:
        db.close()
        return utils.j({'error': True, 'message': "Username already in use."}), 400
    
    email_token = utils.rand_chars(48)
    current_time = int(time.time())

    db.insert('users', [
        request_data['username'].lower(),
        request_data['username'],
        request_data['email'],
        hasher.hash(request_data['password']),
        email_token,
        'User',
        f'["{request.access_route[0]}"]',
        current_time
    ])
    db.close()

    mail.send(request_data['email'], mail.register_subject, mail.register_content.format(email_token))

    utils.admin_webhook(f'New Site Signup `{request_data["username"]}` `{request.access_route[0]}`')

    return utils.j({'error': False, 'message': "Verify your email to continue. Check your Spam Folder."}), 200


def recover_email_send(email, ip):
    db = database.Connection(config.db_name)
    email_search = db.query('users', ['email'], {'email': email})
    if email_search is not None:
        email_token = utils.rand_chars(48)
        mail.send(email, mail.reset_subject, mail.reset_content.format(ip, ip, email_token))
        db.insert('recover', [email_token, email_search[0], int(time.time())])
    db.close()
    

@app.route('/api/v1/auth/recover', methods=['POST'])
@limiter.limit("1 per 2 seconds")
@limiter.limit("1 per 15 seconds", deduct_when=lambda response: response.status_code == 200)
def api_recover():
    try:
        request_data = {
            'email': request.json['email'].lower(),
            'captcha': request.json['token']
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400

    if utils.turnstile(request_data['captcha'], request.access_route[0]) == False:
        return utils.j({'error': True, 'message': "Please try again."}), 400
    
    threading.Thread(target=recover_email_send, args=(request_data['email'], request.access_route[0])).start()
    return utils.j({'error': False, 'message': "Check your email for more information."}), 200


@app.route('/api/v1/auth/reset', methods=['POST'])
@limiter.limit("2 per 1 seconds")
def api_reset():
    try:
        request_data = {
            'type': request.json['type'],
            'key': request.json['key']
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if utils.validate_string(request_data['key'], 'rand_chars', None, None, 48) == False:
        return utils.j({'error': True, 'message': "Invalid Key."}), 400

    db = database.Connection(config.db_name)
    key_data = db.query('recover', ['user', 'time'], {'key': request_data['key']})
    if key_data is None:
        db.close()
        return utils.j({'error': True, 'message': "Invalid Key."}), 400
    
    if key_data[2] + config.reset_password_timeout < int(time.time()):
        db.delete('recover', {'key': request_data['key']})
        db.close()
        return utils.j({'error': True, 'message': "Expired. Try reset password again."}), 400
    
    if request_data['type'] == '1':
        # password reset
        try:
            request_data['password'] = request.json['password']
            request_data['confirm'] = request.json['confirm']
        except:
            return utils.j({'error': True, 'message': "Data Error."}), 400
        
        if request_data['password'] != request_data['confirm']:
            return utils.j({'error': True, 'message': "Passwords don't match."}), 400

        password_hash = hasher.hash(request_data['password'])
        db.edit('users', {'password': password_hash}, {'rowid': key_data[1]})
        
        db.delete('cookies', {'user': key_data[1]})
        db.delete('recover', {'key': request_data['key']})
        
        email_data = db.query('users', ['email'], {'rowid': key_data[1]})
        mail.send(email_data[1], mail.password_change_subject, mail.password_change_content.format(request.access_route[0], request.access_route[0]))
        db.close()

        return utils.j({'error': False, 'message': "Password changed!"}), 200

    else:
        # validate key
        db.close()
        return utils.j({'error': False}), 200


@app.route('/api/v1/auth/verify', methods=['POST'])
@limiter.limit("2 per 1 seconds")
def api_verify():
    try:
        request_data = {
            'key': request.json['key'],
            'captcha': request.json['token']
        }
    except:
        return utils.j({'error': True, 'message': "Data Error."}), 400
    
    if utils.validate_string(request_data['key'], 'rand_chars', None, None, 48) == False:
        return utils.j({'error': True, 'message': "Invalid Key."}), 400

    if utils.turnstile(request_data['captcha'], request.access_route[0]) == False:
        return utils.j({'error': True, 'message': "Please try again."}), 400
    
    db = database.Connection(config.db_name)
    discover_query = db.query2('SELECT rowid, email_verified, ips FROM users WHERE email_verified LIKE ? OR ips LIKE ?', [f'%{request_data["key"]}%', f'%{request_data["key"]}%'], True)

    if discover_query is None:
        db.close()
        return utils.j({'error': True, 'message': "Unknown Key."}), 400
    
    if request_data['key'] in discover_query[1]:
        # email verification
        db.edit('users', {'email_verified': 'True'}, {'rowid': discover_query[0]})
        
        cookie = utils.rand_chars(64)
        db.insert('cookies', [cookie, discover_query[0], int(time.time()), request.headers.get('User-Agent'), request.access_route[0]])
        db.close()
        res = flask.make_response(utils.j({'error': False, 'message': "Email Verified!", "div": "continue-div"}))
        res.set_cookie("ssid", value=cookie, max_age=config.cookie_timeout)
        return res, 200
    
    elif request_data['key'] in discover_query[2]:
        # ip verification
        user_ips = json.loads(discover_query[2])
        ip_data = None
        for user_ip in user_ips:
            if request_data['key'] in user_ip:
                ip_data = user_ip # ip:token
                break
        
        if ip_data is None: # shouldnt happen
            
            return utils.j({'error': True, 'message': "Unknown Key."}), 400
        
        user_ips.remove(ip_data)
        user_ips.append(ip_data.split('/')[0])

        db.edit('users', {'ips': utils.j(user_ips)}, {'rowid': discover_query[0]})
        db.close()
        
        return utils.j({'error': False, 'message': "IP Address Authorized! Please try logging in again.", "div": "login-div"}), 200

    else:
        # "wtf happened here" verification
        db.close()
        return utils.j({'error': True, 'message': "Unknown Key."}), 400