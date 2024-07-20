# Members Site

This site was responsible for customers purchasing:
- Offline Members
- Online Members
- Boost Members / Server Boosts

This is my more favourable site, in terms of code quality.

The `private` folder contains the backend, and the `public` folder contains the front end.


## `public`
This was hosted directly onto Cloudflare Pages on a GitHub repo. Not much else to it.



## `private`
Here's the juicy stuff.

The backend is quite nicely designed if I do say so myself. Whilst there probably is a few code smells and other general issues, it's a lot better than the nitro site's backend.


### Site-wide Authentication
JWT's are pretty much used everywhere in this site.

Wrappers are used on requests that require auth, instead of pasting functions at the beginning of every request (like nitro site).


### Oauth-ing with Discord
Members were added to servers using the "Join Servers for You" permission on Discord. This means that the whole process contains **zero hCaptchas**, making it a whole lot more reliable.

Code wise, it uses a lot of classes. Take a look at the `Token` class in `oauth/token.py` if you're curious. It's quite big.

It's well known now that you need a clean TLS handshake if you want to selfbot on Discord. `oauth/http.py` deals with that, by making a different client for each token (so they each have a random order of extensions).


### Creating a REST-ful(ish) API
If you take a look in the `web/api/` folder, all endpoints are seperating into their respective resource (`user`, `oauth`, `auth`). This just makes development that much easier.


### Admin Dashboard
The dashboard was how we added tokens, and managed stock, and other admin stuff. It contained a live feed of all logs on the server, and also past logs were viewable. A table of tokens was also present, where you can perform bulk actions on the tokens.