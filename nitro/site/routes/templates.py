from main import app, limiter
import utils, database, config

from flask import request, render_template
import flask

@app.route('/test')
@limiter.limit("6 per 2 seconds")
def test():
    raise Exception('balls')

@app.route('/login')
@limiter.limit("6 per 2 seconds")
def login():
    user_id = utils.authenticate(request)
    if user_id != False:
        return utils.redirect('index')
    
    return render_template('login.html')

@app.route('/register')
@limiter.limit("6 per 2 seconds")
def register():
    user_id = utils.authenticate(request)
    if user_id != False:
        return utils.redirect('index')
    
    return render_template('register.html')

@app.route('/recover')
@limiter.limit("6 per 2 seconds")
def recover():
    return render_template('recover.html')

@app.route('/reset')
@limiter.limit("6 per 2 seconds")
def reset():
    return render_template('reset.html')

@app.route('/qrcode')
@limiter.limit("6 per 2 seconds")
def qrcode():
    return render_template('qr_code.html')

@app.route('/verify')
@limiter.limit("6 per 2 seconds")
def verify():
    return render_template('verify.html')

@app.route('/')
@limiter.limit("6 per 2 seconds")
def index():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    return render_template('index.html')

@app.route('/logout')
@limiter.limit("6 per 2 seconds")
def logout():
    res = flask.make_response()
    res.set_cookie("ssid", value="", max_age=0)
    res.headers['location'] = flask.url_for('login')
    return res, 302

@app.route('/settings')
@limiter.limit("6 per 2 seconds")
def settings():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    return render_template('settings.html')

@app.route('/faq')
@limiter.limit("6 per 2 seconds")
def faq():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    return render_template('faq.html')

@app.route('/purchase')
@limiter.limit("6 per 2 seconds")
def purchase():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    db = database.Connection(config.db_name)
    username = db.query('users', ['username'], {'rowid': user_id})
    db.close()
    if username is None:
        return utils.redirect('login')

    return render_template('purchase.html', username=username[1])

@app.route('/ticket-create')
@limiter.limit("6 per 2 seconds")
def ticket_create():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    return render_template('ticket-create.html')

@app.route('/paypal')
@limiter.limit("6 per 2 seconds")
def paypal():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    return render_template('paypal.html')

@app.route('/admin')
@limiter.limit("6 per 2 seconds")
def admin():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')
    
    db = database.Connection(config.db_name)
    if db.query('users', ['role'], {'rowid': user_id})[1] != 'User':
        db.close()
        return render_template('admin.html')
    db.close()
    return utils.redirect('index')

@app.route('/ticket')
@limiter.limit("6 per 2 seconds")
def ticket():
    user_id = utils.authenticate(request)
    if user_id == False: return utils.redirect('login')

    if request.args.get('id') is not None:
        return render_template('ticket.html')
    return utils.redirect('index')