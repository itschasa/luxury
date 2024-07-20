import websocket

ws = websocket.WebSocket()
ws.connect('ws://localhost:6983/api/v1/users/@me/tickets/websocket?id=0045', timeout=3)
print(ws.recv())

