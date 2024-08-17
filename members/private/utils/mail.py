from queue import Queue
import logging
import ssl
import smtplib

from config import config



log = logging.getLogger("backend")


email_queue = Queue()

register_subject = 'Verify your Email | LuxuryNitro - Member + Server Boosting'
register_content = """Hey there,

You're one step away from creating your account!
Verify your email by using the link:

https://mem.luxurynitro.com/verify?key={}

Thanks,
LuxuryNitro"""

verify_subject = 'New Login Location | LuxuryNitro - Member + Server Boosting'
verify_content = """Hey there,

Someone tried to log into your account!
IP Address: {}
More Info: https://ipinfo.io/{}

If this was you, then click the link below:
https://mem.luxurynitro.com/verify?key={}

If this wasn't you, then you need to change your password ASAP.

Thanks,
LuxuryNitro"""

reset_subject = 'Password Reset | LuxuryNitro - Member + Server Boosting'
reset_content = """Hey there,

Someone requested to reset your password!
IP Address: {}
More Info: https://ipinfo.io/{}

If this was you, then click the link below:
https://mem.luxurynitro.com/verify?key={}

If this wasn't you, then you can safely delete this email.

Thanks,
LuxuryNitro"""

password_change_subject = 'Password Changed | LuxuryNitro - Member + Server Boosting'
password_change_content = """Hey there,

Your password has been changed!
IP Address: {}
More Info: https://ipinfo.io/{}

If this wasn't you, reset your password on https://mem.luxurynitro.com/recover and on your email!

Thanks,
LuxuryNitro"""


def thread_mail():
    while True:
        data = email_queue.get()
        success = False
        errors = []
        for _ in range(3):
            try:
                ssl_context = ssl.create_default_context()
                service = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context)
                service.login(data[0], data[1])
                
                service.sendmail(data[0], data[2], data[3])
                
                service.quit()
            except Exception as e:
                errors.append(e)
                pass
            else:
                success = True
                break
        
        if not success:
            log.error(f"Failed to send email to {data[2]}: {errors}")
        

def send(email, subject, content):
    email_queue.put([config().email.address, config().email.password, email, f"From: LuxuryNitro <{config().email.address}>\nTo: {email}\nSubject: {subject}\n\n{content}"])
