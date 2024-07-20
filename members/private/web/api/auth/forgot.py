from flask import request
from flask import jsonify

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@limiter.limit('1 per minute', deduct_when=lambda r: r.status_code == 200 or r.status_code == 401)
@app.route('/api/v1/auth/forgot/send', methods=['POST'])
@utils.force_json
def route_forgot_send():
    try:
        request_data = {
            'email':    utils.typ(request.json['email'], str),
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
    
    # Validate email
    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT email, verified, id FROM users WHERE email = ?;',
            [request_data['email']]
        )
        raw_data = cur.fetchone()
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    if raw_data:
        # Check if user is verified
        if raw_data[1] != 1:
            return jsonify({'error': True, 'message': "This email hasn't been verified. Check your email for a verification code."}), 401

        utils.mail.send(
            raw_data[0],
            utils.mail.reset_subject,
            utils.mail.reset_content.format(
                request.access_route[0],
                request.access_route[0],
                auth.generate_jwt(auth.VerifyPayload(
                    raw_data[2],
                    2,
                    f"{request.access_route[0]};{raw_data[0]}"
                ))
            )
        )
    
    return jsonify({'error': False, 'message': 'If this email was on record, we have sent an email to your mailbox.'}), 200


@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/auth/forgot/change', methods=['POST'])
@utils.force_json
def route_forgot_change():
    try:
        request_data = {
            'password':  utils.typ(request.json['password'], str),
            'key':       utils.typ(request.json['key'], str)
        }
    except KeyError:
        return jsonify({'error': True, 'message': 'Bad Request.'}), 400
    
    # Validate key
    key_payload = auth.authorise_jwt(request_data['key'], 2)
    if not key_payload.validated or key_payload.type != 3:
        return jsonify({'error': True, 'message': 'Invalid or expired key.'}), 400
    
    if key_payload.data != request.access_route[0]:
        return jsonify({'error': True, 'message': 'Invalid or expired key.'}), 400

    # Change password, and fetch user's email
    new_pwd = utils.hasher.hash(request_data['password'])
    current_time = utils.ms()

    conn, cur = db.pool.get()
    try:
        cur.execute(
            'SELECT display_name, email FROM users WHERE id = ?;',
            [key_payload.user_id]
        )
        raw_data = cur.fetchone()
        
        cur.execute(
            'UPDATE users SET password = ?, kickoff_time = ? WHERE id = ?;',
            [new_pwd, current_time, key_payload.user_id]
        )
    except db.error as exc:
        db.pool.release(conn, cur)
        raise exc
    
    db.pool.release(conn, cur)

    auth.clean_kickoff_cache(key_payload.user_id)

    # Send email
    utils.mail.send(
        raw_data[1],
        utils.mail.password_change_subject,
        utils.mail.password_change_content.format(
            request.access_route[0],
            request.access_route[0]
        )
    )

    # Generate JWT
    auth_jwt = auth.generate_jwt(
        auth.AuthPayload(
            key_payload.user_id,
            raw_data[0],
            utils.snowflake.time(key_payload.user_id)
        )
    )

    utils.log.info(f'user {key_payload.user_id} changed password on {request.access_route[0]}')
    
    return jsonify({'error': False, 'message': 'Password changed! Logging you in...', 'jwt': auth_jwt, 'action': 'login'}), 200
