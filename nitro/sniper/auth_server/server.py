import pyDH, base64, json, binascii

from colorama import Fore

from flask import Flask, request
from flask_sock import Sock

import database

import os
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

import logging
import datetime

stdout_log_level = logging.DEBUG
file_log_level = logging.DEBUG
file_log_name = '{:%Y-%m-%d %H.%M.%S}.log'.format(datetime.datetime.now())

class CustomFormatter(logging.Formatter):
    grey = Fore.LIGHTBLACK_EX
    yellow = Fore.YELLOW
    red = Fore.LIGHTRED_EX
    bold_red = Fore.RED
    reset = Fore.RESET
    format = "%(asctime)s - %(levelname)s: %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: reset + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
      
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(stdout_log_level)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

file_handler = logging.FileHandler(file_log_name)
file_handler.setLevel(file_log_level)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s (%(filename)s:%(lineno)d)'))
logger.addHandler(file_handler)


f = open('server.key', 'rb')
server_rsa = RSA.import_key(f.read())
f.close()
signer = pkcs1_15.new(server_rsa)

def sign_message(message:bytes) -> str:
    "outputs base64 signiture"
    h = SHA256.new(message)
    return base64.b64encode(signer.sign(h)).decode()

f = open('server.pub', 'rb')
pub_key_hash = SHA256.new(f.read()).hexdigest()
f.close()

def aes_cbc_encrypt(message, secret_key_hex):
    secret_key = binascii.unhexlify(secret_key_hex)
    padded_message = message.encode('utf-8') + b"\0" * (16 - len(message.encode('utf-8')) % 16)
    iv = get_random_bytes(16)
    cipher = AES.new(secret_key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded_message)
    return binascii.hexlify(iv).decode() + binascii.hexlify(ciphertext).decode()

def aes_cbc_decrypt(ciphertext_combo, secret_key_hex):
    ciphertext = binascii.unhexlify(ciphertext_combo[32:])
    iv = binascii.unhexlify(ciphertext_combo[:32])
    secret_key = binascii.unhexlify(secret_key_hex)
    cipher = AES.new(secret_key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    message = decrypted.rstrip(b"\0").rstrip(b"\x10")
    return message.decode()


app = Flask(__name__)
sock = Sock(app)

# /auth?h=(sha256 of server.pub)
@sock.route('/auth')
def auth_ws(ws):
    logger.debug(f"Connection Inbound [/auth, {request.access_route[0]}]")
   
    if pub_key_hash != request.args.get('h'):
        logger.warning(f"Unacceptable Hash [/auth, {request.access_route[0]}]")
        return '400'

    server_key = pyDH.DiffieHellman(14)
    server_pubkey = server_key.gen_public_key()

    hello = json.dumps({
        "k": str(server_pubkey),
        "s": sign_message(str(server_pubkey).encode())
    })
    ws.send(hello)
    logger.debug(f"SENT Hello [/auth, {request.access_route[0]}]")

    reply_raw = ws.receive(timeout=10)
    if reply_raw == None:
        logger.warning(f"No Reply [/auth, {request.access_route[0]}]")
        ws.close()
        return
    logger.debug(f"RECEIVE Hello [/auth, {request.access_route[0]}]")

    reply = json.loads(reply_raw)
    
    client_pubkey = int(reply['k']) # int
    verify_secret_cipher = reply['v'] # encrypted message, str hex
    verify_secret_plain = reply['n'] # random str hex, nonce

    shared_secret = server_key.gen_shared_key(client_pubkey)

    verify_secret = aes_cbc_decrypt(verify_secret_cipher, shared_secret)
    if verify_secret == verify_secret_plain:
        logger.debug(f"Good Secret [/auth, {request.access_route[0]}]")
        ws.send('1')
        
        op_auth = ws.receive(timeout=10)
        if op_auth == None:
            logger.warning(f"No Reply [/auth, {request.access_route[0]}]")
            ws.close()
            return
        else:
            try:
                data_json = json.loads(aes_cbc_decrypt(op_auth, shared_secret))
            except:
                logger.debug(f"Bad Decrypt [/auth, {request.access_route[0]}]")
                ws.close()
                return
            else:
                db = database.Base('database.db')
                hwid_lookup = db.query('clients', ['user', 'expires', 'auth', 'data'], {'license': data_json['d']['license']})
                db.close()
                if hwid_lookup == None:
                    final_data = {'op': 'auth', 'status': 'failed', 'message': 'Invalid License'}
                else:
                    if hwid_lookup[1] != data_json['d']['hwid']:
                        final_data = {'op': 'auth', 'status': 'failed', 'message': 'Invalid HWID'}
                    else:
                        final_data = {'op': 'auth', 'status': 'success', 'message': 'Logged in!'}
                
                ws.send(aes_cbc_encrypt(json.dumps(final_data), shared_secret))
                ws.close()
                logger.info(f"SENT Auth [/auth, {request.access_route[0]}, {final_data['status']}, {final_data['message']}]")
                return
    else:
        logger.warning(f"Bad Secret [/auth, {request.access_route[0]}]")
        ws.send('0')
        ws.close()


app.run('0.0.0.0', 8069)