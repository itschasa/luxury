import httpx, time

r = httpx.post('http://localhost:6983/api/v1/sniper',
    json={
        "type": 1,
        "token": "ODU4MTk1OD***",
        "time": "123.56789ms",
        "snipe": "Nitro Monthly"
    },
    headers = {
        'authorization': "***",
        'x-instance-id': '123'
    }
)
print(r.text)