## Sniper

This sniper was designed to be used for both our site, and also for customers to use to make their own sniper setup. However, this never happened.

Hence why the `RunAuth()` in `main()` is commented out.

This sniper is by no means the best, fastest, or even good. But it worked for us, so that's all that really mattered for us.

I spent too long trying to get the sniper's auth working in Go, for it to eventually never be used. Oh well :3

---
### What is `enc_tokens.txt`?
Well, we once had a shared vps with another person, so we had to get a way to store the tokens safely on it. I know the encryption key `luxuryandchasaarethecutestcouple` isn't exactly *secure*. But it didn't need to be, as this source code was never public.

---
### Connecting to the web server
Have a read of the site [readme](https://github.com/itschasa/luxury/blob/main/nitro/site/README.md#conecting-the-sniper-with-the-web-server).