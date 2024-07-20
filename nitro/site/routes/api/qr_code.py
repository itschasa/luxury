from main import app, limiter, sock
import database
import utils, config

from flask import request
import websocket
import base64
import json
import threading
import time

import qrcode, io
import websocket
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

class Messages:
    HEARTBEAT = 'heartbeat'
    HELLO = 'hello'
    INIT = 'init'
    NONCE_PROOF = 'nonce_proof'
    PENDING_REMOTE_INIT = 'pending_remote_init'
    PENDING_TICKET = 'pending_ticket'
    PENDING_LOGIN = 'pending_login'
    CANCEL = 'cancel'

ws_connections = {}

def heartbeat_thread():
    global ws_connections
    while True:
        time.sleep(3)
        current_time = int(time.time())
        for id, ws in ws_connections.copy().items():
            if current_time > ws['last_hb'] + 30:
                try:
                    ws['dc_ws'].send(utils.j({'op': 'heartbeat'}))
                except: pass
                else:
                    ws_connections[id]['last_hb'] = current_time

def decrypt_payload(encrypted_payload, cipher):
    payload = base64.b64decode(encrypted_payload)
    return cipher.decrypt(payload)

def ws_connect(ws_id):
    global ws_connections
    
    ws = ws_connections[ws_id]['ws']

    key = RSA.generate(2048)
    cipher = PKCS1_OAEP.new(key, hashAlgo=SHA256)
    ws_connections[ws_id]['cipher'] = cipher
    public_key = key.publickey().export_key().decode('utf-8')
    public_key = ''.join(public_key.split('\n')[1:-1])

    dc_ws = websocket.WebSocket()
    dc_ws.connect("wss://remote-auth-gateway.discord.gg/?v=2", header={'Origin': 'https://discord.com'})
    dc_ws.sock.settimeout(60)
    ws_connections[ws_id]['dc_ws'] = dc_ws

    while True:
        try:
            message = dc_ws.recv()
        except websocket.WebSocketTimeoutException:
            try:
                ws_connections[ws_id].send(utils.j({'op': 'close', 'reason': 'Discord Timeout.'}))
            except:
                pass
            try:
                del ws_connections[ws_id]
            except:
                pass
            break
        else:
            try: recv_json = json.loads(message)
            except: return # ws has been closed (probably)
            op = recv_json.get('op')

            if op == Messages.HELLO:
                dc_ws.send(utils.j({'op': Messages.INIT, 'encoded_public_key': public_key}))

            elif op == Messages.NONCE_PROOF:
                nonce = recv_json.get('encrypted_nonce')
                decrypted_nonce = decrypt_payload(nonce, cipher)

                proof = SHA256.new(data=decrypted_nonce).digest()
                proof = base64.urlsafe_b64encode(proof)
                proof = proof.decode().rstrip('=')
                dc_ws.send(utils.j({'op': Messages.NONCE_PROOF, 'proof': proof}))

            elif op == Messages.PENDING_REMOTE_INIT:
                fingerprint = recv_json.get('fingerprint')
                qr_code_url = f'https://discordapp.com/ra/{fingerprint}'
                qr = qrcode.QRCode(version=1, box_size=10, border=1)
                qr.add_data(qr_code_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img_bytes = io.BytesIO()
                img.save(img_bytes)
                img_bytes.seek(0)
                img_base64 = "data:image/png;base64," + base64.b64encode(img_bytes.getvalue()).decode("ascii")
                ws.send(utils.j({"op": "qrcode", 'd': img_base64}))


            elif op == Messages.PENDING_TICKET:
                encrypted_payload = recv_json.get('encrypted_user_payload')
                payload = decrypt_payload(encrypted_payload, cipher).decode().split(':')
                ws.send(utils.j({'op': 'data', 'd': {'id': payload[0], 'discrim': payload[1], 'avatar': payload[2], 'user': payload[3]}}))

            elif op == Messages.PENDING_LOGIN:
                ticket = recv_json.get('ticket')
                ws.send(utils.j({'op': 'ticket', 'd': ticket}))
            
            elif op == Messages.CANCEL:
                dc_ws.close()
                ws.send(utils.j({'op': 'close', 'reason': 'Cancelled by User.'}))
                try:
                    del ws_connections[ws_id]
                except:
                    pass
                ws.close()
                break


@sock.route('/api/v1/qr_code')
@limiter.limit("1 per 2 seconds")
def api_qr_code(ws):
    global ws_connections
    
    ws_id = utils.rand_chars(8)
    ws_connections[ws_id] = {
        'ws': ws,
        'dc_ws': None,
        'last_hb': 0,
        'cipher': None
    }

    threading.Thread(target=ws_connect, args=(ws_id,)).start()

    while True:
        try:
            data = ws.receive(timeout=10)
            if data is None:
                raise Exception
        except:
            try: ws_connections[ws_id]['dc_ws'].close()
            except: pass
            try: del ws_connections[ws_id]
            except: pass
            try: ws.close()
            except: pass
            break
        else:
            data_json = json.loads(data)
            if data_json['op'] == 'token':
                ws.send(utils.j({'op': 'token', 'd': decrypt_payload(data_json['d'], ws_connections[ws_id]['cipher']).decode()}))
                try: ws_connections[ws_id]['dc_ws'].close()
                except: pass
                try: del ws_connections[ws_id]
                except: pass
                try: ws.close()
                except: pass
                break
    
    try: del ws_connections[ws_id]
    except: pass
