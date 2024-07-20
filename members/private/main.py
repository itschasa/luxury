import threading
from gevent.pywsgi import WSGIServer
from gevent import monkey
monkey.patch_all()

import config
from web.app import app
from web.api import *
from utils.mail import thread_mail
from oauth import thread_guild_checker, thread_order_handler, startup_add_to_queue



threading.Thread(target=thread_mail, daemon=True).start()
threading.Thread(target=thread_guild_checker, daemon=True).start()
threading.Thread(target=thread_order_handler, daemon=True).start()


startup_add_to_queue()

http_server = WSGIServer(("127.0.0.1", 19283), app)
http_server.serve_forever()
