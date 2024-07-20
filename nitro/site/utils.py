import database
import random, httpx, config, time, json, flask, tls_client, re, traceback
import brotli
from main import app

session = tls_client.Session(client_identifier='chrome_111')
token_regex = r"([\w-]{20,26}\.(([\w-]{5,8}\.[\w-]{27,45})|([\w-]{40,50})))|(mfa\.[\w-]{84})"

def clean_id(id):
    return ('{}'+str(id)).format(''.join('0' for _ in range(4 - len(str(id)))))

def admin_webhook(content):
    try:
        f = open('globals/adminwebhook.txt')
        discord_webhook_url = f.read()
        f.close()
        
        httpx.post(discord_webhook_url, json={
            'content': content
        })
    except:
        pass

    
def check_token(token):
    if not re.findall(token_regex):
        return 'Invalid Token. (Regex)'
    
    headers = {
        "accept": "*/*",
        "accept-encoding": "identity",
        "accept-language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "authorization": token,
        "cookie": "locale=en-GB",
        "referer": "https://discord.com/channels/@me",
        "sec-ch-ua": '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "x-debug-options": "bugReporterEnabled",
        "x-discord-locale": "en-GB",
        "x-super-properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzExMS4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTExLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjE4NDM0NCwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbCwiZGVzaWduX2lkIjowfQ=="
    }

    req = session.post("https://discord.com/api/v9/entitlements/gift-codes/" + rand_chars(16) + "/redeem", headers={**headers, 'origin': 'https://discord.com'}, data=r"{}")
    if req.headers.get("Content-Type") == 'application/json':
        if req.status_code in [200, 201, 202, 203, 204, 404]:
            req = session.get('https://discord.com/api/v9/users/@me', headers=headers)
            js: dict = req.json()
            
            if js.get('phone') is None:
                return 'No phone linked to Discord Account.'
            
            return True
        elif req.status_code == 403:
            if req.json()['code'] == 40002: # "You need to verify your account in order to perform this action." 🤓
                if 'e-mail' in req.json()['message']:
                    return 'Token requires email verification.'
                return 'Token is Locked.'
            else:
                return 'Invalid Token. (403)'
        elif req.status_code == 401:
            return 'Invalid Token. (401)'
        elif req.status_code == 429:
            return 'Please try again.'
        elif str(req.status_code).startswith("5"):
            return False
        else:
            return f'Invalid Token. ({req.status_code})'
    else:
        # discord server error, just wait
        return False

def rand_chars(length):
    return ''.join(random.choice("QWERTYUIOPLKJHGFDSAZXCVBNM1234567890qwertyuioplkjhgfdsazxcvbnm") for _ in range(length))

def turnstile(token, ip):
    try:
        req = httpx.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data={
            'secret': config.turnstile_secret,
            'response': token,
            'sitekey': config.turnstile_public,
            'remoteip': ip
        }).json()
    except:
        return False
    else:
        return req['success']

def validate_string(string, type, minlength, maxlength, setlength=None):
    if string is None:
        return None
    
    if type == "username":
        if string.lower() == 'system' or string.lower() == 'anonymous':
            return None
        
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm_.-"
    elif type == "email":
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm@-_."
    elif type == "rand_chars":
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm"
    elif type == "api":
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm_"
    else:
        chars = "1234567890qwertyuioplkjhgfdsazxcvbnm_.:;\"@-<=>?!()}[]{#£$%^&*^',/\\|~` "
    
    if setlength is None:
        if minlength is not None:
            if len(string) < minlength:
                return False
        
        if maxlength is not None:
            if len(string) > maxlength:
                return False
    else:
        if len(string) != setlength:
            return False
        
    for char in string.lower():
        if char not in chars:
            return None
    
    return True

def j(d):
    return json.dumps(d)

def redirect(func):
    res = flask.make_response()
    res.headers['location'] = flask.url_for(func) 
    return res, 302

auth_cache = {}

def get_cookie_data(cookie):
    global auth_cache
    
    cookie_data = auth_cache.get(cookie)
    if cookie_data is None:
        db = database.Connection(config.db_name)
        cookie_data = db.query('cookies', ['user', 'time', 'agent', 'ip'], {'cookie': cookie})
        db.close()
        if cookie_data is None:
            return None
        else:
            auth_cache[cookie] = cookie_data

    return cookie_data

def authenticate(req):
    cookie = req.cookies.get('ssid')
    agent = req.headers.get('User-Agent')
    ip = req.access_route[0]

    if validate_string(cookie, 'rand_chars', None, None, 64) is False and validate_string(cookie, 'api', None, None, 36) is False:
        return False
    else:
        cookie_data = get_cookie_data(cookie)
        
        if cookie_data is None:
            return False
        else:
            time_rn = time.time()
            if int(time_rn) > int(cookie_data[2]) + config.cookie_timeout:
                return False
            else:
                if (agent == cookie_data[3] and ip == cookie_data[4]) or cookie.startswith('api_'):
                    return cookie_data[1]
                else:
                    return False
                
def xss_safe(text : str):
    if '<' in text and '>' in text:
        return text.replace('<', '').replace('>', '')
    return text
    
def gen_verify_code():
    integer = str(random.randint(1,999999))
    for _ in range(6 - len(integer)):
        integer = '0' + integer
    return integer

def send_feedback_webhook(txt):
    try:
        f = open('globals/feedbackwebhook.txt')
        webhook_url = f.read()
        f.close()
        httpx.post(webhook_url, json={
            "embeds": [
                {
                    "description": txt,
                    "color": 6504439
                }
            ],
            "username": "Feedback",
            "attachments": []
        })
    except:
        app.logger.error(traceback.format_exc())

def send_order_webhook(txt):
    try:
        f = open('globals/orderwebhook.txt')
        webhook_url = f.read()
        f.close()
        httpx.post(webhook_url, json={
            "embeds": [
                {
                    "description": txt,
                    "color": 10574079
                }
            ],
            "username": "Orders",
            "attachments": []
        })
    except:
        app.logger.error(traceback.format_exc())

def convertHMS(value):
    sec = int(value)  # convert value to number if it's a string
    hours = sec // 3600  # get hours
    minutes = (sec - (hours * 3600)) // 60  # get minutes
    seconds = sec - (hours * 3600) - (minutes * 60)  # get seconds
    if hours > 0:
        hours = str(hours) + 'hr '
    else:
        hours = ''
    if minutes > 0:
        minutes = str(minutes) + 'm '
    else:
        minutes = ''
    if seconds > 0:
        seconds = str(seconds) + 's'
    else:
        if hours == '' and minutes == '':
            seconds = str(seconds) + 's'
        else:
            seconds = ''
    if (hours + minutes + seconds).endswith(' '):
        return (hours + minutes + seconds)[:-1]
    return hours + minutes + seconds

def tidy_tokens():
    while True:
        db = database.Connection(config.db_name)
        res = db.query2("SELECT referral, token FROM orders WHERE token LIKE ? AND status = ?", ['%.%', '2'], False)
        for order in res:
            db.edit("orders", {'token': order[1].split('.')[0]}, {'referral': order[0]})
        db.close()
        time.sleep(20)

def trigger_basic_refund(order_id):
    db = database.Connection(config.db_name)
    order = db.query('orders', ['user', 'quantity', 'claim_data'], {'referral': order_id})
    if order:
        claim_data: list[dict] = json.loads(order[3])
        fake_nitros = 0
        for claim in claim_data:
            if 'Boost' not in claim['type']:
                fake_nitros += 1
        
        cleaned_order_id = clean_id(order_id)

        reward = fake_nitros // 3
        if reward > 0:
            balance = db.query2('SELECT balance FROM credits WHERE user = ? ORDER BY rowid DESC', [order[1]], True)
            balance = 0 if balance is None else balance[0]
            
            db.insert('credits', [str(reward), order[1], f'Basics from #{cleaned_order_id} (Auto)', balance + reward, int(time.time())])
            
            app.logger.info(f'Basic Refund: #{cleaned_order_id} (+{reward})')
        else:
            app.logger.info(f'No Basic Refund: #{cleaned_order_id}')
        
        db.close()
        return True

    else:
        db.close()
        return False