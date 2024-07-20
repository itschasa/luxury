import os
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

# Generate RSA key pair
key = RSA.generate(2048)

# Write private key to a file
with open('server.key', 'wb') as f:
    f.write(key.export_key('PEM'))

# Write public key to a file
with open('server.pub', 'wb') as f:
    f.write(key.publickey().export_key('PEM'))
