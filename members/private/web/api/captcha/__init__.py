from flask import request
from flask import jsonify

from web.app import app, limiter
import utils



@limiter.limit('1 per second')
@app.route('/api/v1/captcha', methods=['GET'])
def route_captcha():
    captcha = utils.Captcha(request.access_route[0])
    return jsonify({'jwt': captcha.to_jwt(), 'cd': captcha.cdata, 'key': captcha.site_key}), 200
