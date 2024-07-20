from flask import request
from flask import jsonify

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@limiter.limit('3 per minute', deduct_when=lambda r: r.status_code == 200)
@app.route('/api/v1/auth/login', methods=['POST'])
@utils.force_json
def route_login():
    try:
        request_data = {
            'email':    utils.typ(request.json['email'], str),
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
    
    # Validate email and password
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT id, name, ips, verified, email, password FROM users WHERE email = ?;',
            [request_data['email']]
        )
        raw_data = cur.fetchone()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)
    if not raw_data:
        return jsonify({'error': True, 'message': 'Invalid email or password.'}), 400
    
    if not utils.hasher.check(request_data['password'], raw_data[5]):
        return jsonify({'error': True, 'message': 'Invalid email or password.'}), 400

    # Check if user is verified (both IP and email)
    if raw_data[3] != 1:
        return jsonify({'error': True, 'message': 'You need to verify your email before logging in.'}), 400

    if raw_data[2] != '0': # "0" means that user has IP verification disabled
        if request.access_route[0] not in utils.jl(raw_data[2]):
            utils.mail.send(
                raw_data[4],
                utils.mail.verify_subject,
                utils.mail.verify_content.format(
                    request.access_route[0],
                    request.access_route[0],
                    auth.generate_jwt(auth.VerifyPayload(
                        raw_data[0],
                        0,
                        request.access_route[0]
                    ))
                )
            )
            return jsonify({'error': True, 'message': 'Check your email address for a verification link.'}), 400

    # Generate JWT
    auth_jwt = auth.generate_jwt(
        auth.AuthPayload(
            raw_data[0],
            raw_data[1],
            utils.snowflake.time(raw_data[0])
        )
    )

    utils.log.info(f'user {raw_data[1]} logged in from IP {request.access_route[0]}')
    
    return jsonify({'error': False, 'message': 'Logging you in...', 'jwt': auth_jwt}), 200
