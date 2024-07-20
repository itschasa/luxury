from main import app
from flask import send_from_directory

@app.route('/assets/<path:path>')
def assets(path):
    return send_from_directory('assets', path)