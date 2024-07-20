from flask import request
from flask import jsonify

from web.app import app, limiter
import web.api.auth as auth
import utils
import db



@limiter.limit('1 per second')
@limiter.limit('15 per minute')
@app.route('/api/v1/auth/verify', methods=['POST'])
@utils.force_json
def route_verify():
    try:
        request_data = {
            'captcha':  utils.typ(request.json['captcha'], str),
            'jwt':      utils.typ(request.json['jwt'], str),
            'key':      utils.typ(request.json['key'], str)
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
        utils.log.debug(f'CAPTCHA failed: {captcha_result.reason}')
        return jsonify({'error': True, 'message': 'CAPTCHA was invalid, or expired. Please try again.'}), 400
    
    # Validate key
    key_payload = auth.authorise_jwt(request_data['key'], 2)
    if not key_payload.validated:
        return jsonify({'error': True, 'message': 'Invalid or expired key.'}), 400
    
    # Grant access
    conn, cur = db.pool.get()
    if key_payload.type == 0:
        # Add IP to user's list of IPs
        try:
            cur.execute(
                'SELECT ips, display_name FROM users WHERE id = ?;',
                [key_payload.user_id]
            )
            user_data = cur.fetchone()
            if not user_data:
                raise Exception
            
            new_ips = utils.jd([*utils.jl(user_data[0]), key_payload.data])
            cur.execute(
                'UPDATE users SET ips = ? WHERE id = ?;',
                [new_ips, key_payload.user_id]
            )
        except db.error as exc:
            db.pool.release(conn, cur)
            raise exc
        
        db.pool.release(conn, cur)
        
        # Check if IP matches JWT payload
        if key_payload.data == request.access_route[0]:
            auth_jwt = auth.generate_jwt(
                auth.AuthPayload(
                    key_payload.user_id,
                    user_data[1],
                    utils.snowflake.time(key_payload.user_id)
                )
            )

            return jsonify({'error': False, 'message': 'IP verified, logging you in...', 'jwt': auth_jwt, 'action': 'login'}), 200
        else:
            return jsonify({'error': False, 'message': 'IP verified, try logging in again.'}), 200
        
    elif key_payload.type == 1:
        # Set user as verified, and fetch user data
        try:
            cur.execute(
                'SELECT ips, display_name FROM users WHERE id = ?;',
                [key_payload.user_id]
            )
            user_data = cur.fetchone()
            if not user_data:
                raise Exception
            
            cur.execute(
                'UPDATE users SET verified = ? WHERE id = ?;',
                [1, key_payload.user_id]
            )
        except db.error as exc:
            db.pool.release(conn, cur)
            raise exc

        db.pool.release(conn, cur)

        utils.log.info(f'user {key_payload.user_id} verified email on {request.access_route[0]}')
    
        # Check if IP matches JWT payload
        if request.access_route[0] in utils.jl(user_data[0]):
            auth_jwt = auth.generate_jwt(
                auth.AuthPayload(
                    key_payload.user_id,
                    user_data[1],
                    utils.snowflake.time(key_payload.user_id)
                )
            )

            return jsonify({'error': False, 'message': 'Email verified, logging you in...', 'jwt': auth_jwt, 'action': 'login'}), 200
        else:
            return jsonify({'error': False, 'message': 'Email verified, try logging in again.'}), 200
    
    elif key_payload.type == 2:
        key_payload_data = key_payload.data.split(';')
        if key_payload_data[0] != request.access_route[0]:
            return jsonify({'error': True, 'message': 'Invalid or expired key.'}), 400

        forgot_jwt = auth.generate_jwt(
            auth.VerifyPayload(
                key_payload.user_id,
                3,
                key_payload_data[0]
            )
        )
        return jsonify({'error': False, 'message': 'JWT Verified.', 'key': forgot_jwt, 'action': 'reset'}), 200

    else: 
        return jsonify({'error': True, 'message': 'Invalid or expired key.'}), 400
