# Sniper Site

Well, it appears you'll stumble across some terrible code ahead. So, just a heads up. This site's codebase was not well maintained, or kept clean over the year or two it was active.


### HTML + CSS
I used [proxiware](https://proxiware.com/)'s old dashboard as a template when making the site's front end.

---
### Conecting the Sniper with the Web Server
The sniper sends a HTTP request to the web server (endpoint: /api/v1/sniper) every few seconds, asking what token to use, etc, etc.

So, to connect both together, you need to configure the correct URL in the sniper, and to make sure they have the same "auth token" (aka, a long random string).

Setting this on the web server is done in `config.py:sniper_auth`.
```py
sniper_auth = 'your auth token here' # <-----
```

Setting this on the sniper is done inside the code, in `localapi.go:LuxAPIDoReq`.
```go
var request, requestErr = http.NewRequest("POST", "your url here", bytes.NewBuffer([]byte(data))) // <-----

...

request.Header = http.Header{
    "Content-Type": {"application/json"},
    "Connection": {"keep-alive"},
    "Authorization": {"your auth token here"}, // <-----
    "X-Instance-ID": {instance_id},
}
```


## Database
I've added some example data in the `_schema.sql` as comments.

Here's some explaination on some of the columns.

---
### "referral" column in "orders" table
This column contains the real order ID, instead of the rowid.

Seems pretty weird? Well, yes, it is.

We wanted to add a rotating queue system into the site, but using a rowid as the id, and then moving the order of rows around in the db would mess it up. So we used a column we thought we were going to use as the order id, allowing us to change the order of rows in the db, without affecting the order ids.


### "token" column in "orders" table
This could be either 3 values:
- A Discord Token
    - It would be there if the order wasn't complete (status=0|1).
- The first part of a Discord Token (aka, base64 encoded user id)
    - This would let us verify that nitro was received on this account, in case a dispute was raised, and allowed us to keep track of which Discord accounts got nitro.
- "order_completed"
    - Legacy, this was done before we added the point above.


---
### "paypal" table
We tried to add our own automated PayPal gateway, but we decided against it.


---
### "seen_by" column in "ticket_msgs" table
The format is: `-{userid}-`, so we can get the string and do something like this:
```
# some db call here
seen_by = '-1--2--5-'

userid = 1
if f'-{userid}-' in seen_by:
    print('nice')
```

Weird code, yeah I know.

