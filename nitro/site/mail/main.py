from flask import Flask, request
import smtplib, ssl

app = Flask(__name__)

@app.route('/sendemailsecure', methods=['POST'])
def index():
    ssl_context = ssl.create_default_context()
    service = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context)
    service.login(request.json['data'][1], request.json['data'][0])
    
    service.sendmail(request.json['data'][1], request.json['data'][2], request.json['data'][3])

    service.quit()
    return '200'

app.run('0.0.0.0', port=10726)