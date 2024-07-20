import base64

f = open('server.pub', 'rb')
pub_key = f.read()
f.close()

print(base64.b64encode(pub_key).decode())