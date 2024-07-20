from flask import request
from flask import jsonify

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@limiter.limit('1 per minute', deduct_when=lambda r: r.status_code == 200)
@app.route('/api/v1/auth/register', methods=['POST'])
@utils.force_json
def route_register():
    try:
        request_data = {
            'email':    utils.typ(request.json['email'], str).lower(),
            'name':     utils.typ(request.json['name'], str),
            'password': utils.typ(request.json['password'], str),
            'captcha':  utils.typ(request.json['captcha'], str),
            'jwt':      utils.typ(request.json['jwt'], str)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    # Validate JWT + Turnstile
    try:
        captcha = utils.Captcha.from_jwt(request_data['jwt'])
    except utils.turnstile.CaptchaJWTInvalid:
        return jsonify({'error': True, 'message': 'Invalid or expired JWT. Refresh the page.'}), 400
    
    captcha_result = captcha.check(request_data['captcha'], request.access_route[0])
    if not captcha_result.passed:
        return jsonify({'error': True, 'message': 'CAPTCHA was invalid, or expired. Please try again.'}), 400
    
    # Validate email, username, password, and display name
    if not utils.validate_string(request_data['name'], 'username', 3, 32):
        return jsonify({'error': True, 'message': "Username can't contain special characters, and has to between 3-32 characters."}), 400
    
    if not utils.validate_string(request_data['email'], 'email'):
        return jsonify({'error': True, 'message': "Your email looks invalid, please check it's correct."}), 400
    
    if not utils.validate_string(request_data['password'], '', 8, 128):
        return jsonify({'error': True, 'message': 'Passwords have to be between 8-128 characters, and contain no Unicode characters.'}), 400

    request_data['display_name'] = request_data['name']
    request_data['name'] = request_data['name'].lower()
    
    # Check if email or username is already in use
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT email, name FROM users WHERE email = ? OR name = ?;',
            [request_data['email'], request_data['name']]
        )
        raw_data = cur.fetchmany(2) # can only be a maximum of 2: either name, or email is used
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    if len(raw_data) > 0:
        if len(raw_data) == 2:
            db.pool.release(conn, cur)
            return jsonify({'error': True, 'message': 'Email and username already in use.'}), 400
        elif raw_data[0][0] == request_data['email']:
            db.pool.release(conn, cur)
            return jsonify({'error': True, 'message': 'Email already in use.'}), 400
        else:
            db.pool.release(conn, cur)
            return jsonify({'error': True, 'message': 'Username already in use.'}), 400
    
    # Insert user into database
    hashed_pwd = utils.hasher.hash(request_data['password'])
    user_id = utils.snowflake.new()
    try:
        cur.execute(
            '''INSERT INTO users (id, name, email, password, ips, verified, kickoff_time, display_name, api_expire)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);''',
            [user_id, request_data['name'], request_data['email'], hashed_pwd, utils.jd([request.access_route[0]]), 0, 0, request_data['display_name'], 0]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc

    db.pool.release(conn, cur)
    
    # Send verification email
    utils.mail.send(
        request_data['email'],
        utils.mail.register_subject,
        utils.mail.register_content.format(
            auth.generate_jwt(auth.VerifyPayload(
                user_id,
                1,
                expires_at=9999999999999
            ))
        )
    )

    utils.log.info(f'new user {request_data["name"]} registered with email {request_data["email"]} on {request.access_route[0]} (id={user_id})')
    
    return jsonify({'error': False, 'message': 'Registered! Check your email for a verification link.'}), 200
