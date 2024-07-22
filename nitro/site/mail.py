import httpx, threading
import smtplib, ssl


emailAddress = 'noreply.luxuryboosts@gmail.com'
emailPassword = '***'


register_subject = 'Verify your Email | LuxuryNitro'
register_content = """Hey there,

You're one step away from creating your account!
Verify your email by using the link:

https://dash.luxurynitro.com/verify?k={}

Thanks,
LuxuryNitro"""

verify_subject = 'New Login Location | LuxuryNitro'
verify_content = """Hey there,

Someone tried to log into your account!
IP Address: {}
More Info: https://ipinfo.io/{}

If this was you, then click the link below:
https://dash.luxurynitro.com/verify?k={}

If this wasn't you, then you need to change your password ASAP.

Thanks,
LuxuryNitro"""

reset_subject = 'Password Reset | LuxuryNitro'
reset_content = """Hey there,

Someone requested to reset your password!
IP Address: {}
More Info: https://ipinfo.io/{}

If this was you, then click the link below:
https://dash.luxurynitro.com/reset?k={}

If this wasn't you, then you can safely delete this email.

Thanks,
LuxuryNitro"""

password_change_subject = 'Password Changed | LuxuryNitro'
password_change_content = """Hey there,

Your password has been changed!
IP Address: {}
More Info: https://ipinfo.io/{}

If this wasn't you, reset your password on LuxuryNitro (using Forgot Password) and on your email!

Thanks,
LuxuryNitro"""

paypal_subject = 'Verify PayPal Purchase | LuxuryNitro'
paypal_content = """Hey there,

This email was used to purchase credits on PayPal recently.
If this was you, use the code below to verify:

Code: {}

If this wasn't you, please open a ticket on https://dash.luxurynitro.com

Thanks,
LuxuryNitro"""


def sendthread(email, subject, content):
    ssl_context = ssl.create_default_context()
    service = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context)
    service.login(emailAddress, emailPassword)
    
    service.sendmail(emailAddress, email, f"From: LuxuryNitro <{emailAddress}>\nTo: {email}\nSubject: {subject}\n\n{content}")
    
    service.quit()

def send(email, subject, content):
    threading.Thread(target=sendthread, args=(email,subject,content,)).start()