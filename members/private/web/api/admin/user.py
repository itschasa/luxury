from flask import jsonify

from web.app import app, limiter
import web.api.admin as admin
import web.api.auth as auth
import web.api.user as user
import utils
import db



@limiter.limit('1 per second')
@app.route('/api/v1/admin/user/<user_id>', methods=['GET'])
@auth.require_auth
@admin.require_admin
def route_admin_get_user(user_payload: auth.AuthPayload, user_id: str):
    if user_id != '0':
        conn, cur = db.pool.get()
        try:
            cur.execute(
                '''SELECT id, name, email, ips, verified, kickoff_time, display_name, api_expire FROM users
                WHERE id = ?;''',
                [user_id]
            )
            user_raw_data = cur.fetchone()
        except db.error as exc:
            db.pool.release(conn, cur)
            raise exc

        db.pool.release(conn, cur)

        if user_raw_data is None:
            return jsonify({'error': True, 'message': 'User not found.'}), 404

        data = {
            'id':            str(user_raw_data[0]),
            'created_at':    user_payload.user_created_at,
            'name':          user_raw_data[1],
            'email':         user_raw_data[2],
            'ips':           utils.jl(user_raw_data[3]),
            'verified':      user_raw_data[4],
            'kickoff_time':  user_raw_data[5],
            'display_name':  user_raw_data[6],
            'api_expire':    user_raw_data[7],
            'activity':      user.activity.get_activity(user_id),
        }
    else:
        data = {
            'activity': user.activity.get_activity(0),
        }

    return jsonify({'error': False, 'data': data}), 200
