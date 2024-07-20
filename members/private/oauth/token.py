import time
from typing import Union
import traceback
import random
import websocket

from config import config
import oauth
import utils
import db



token_types_dict: dict[int, str] = {
    0: "online",
    1: "offline",
    2: "boost_1month",
    3: "boost_3month"
}

class TokenTypes:
    cost = 0
    def __init__(self, key:int) -> None:
        self.key = key
        self.type_str = token_types_dict[self.key]
        
        self.boost:         bool = self.key in (2, 3)
        
        self.online:        bool = self.key == 0 
        self.offline:       bool = self.key == 1
        self.boost_1month:  bool = self.key == 2
        self.boost_3month:  bool = self.key == 3

        self.cost: Union[int, None] = getattr(config().prices, self.type_str)

    def __str__(self) -> str:
        return self.type_str


token_status_dict = {
    0: "valid",
    1: "invalid",
    2: "locked",
    3: "expired",
    4: "quarantined",
    5: "spammer"
}


def requires_access_token(func):
    def wrapper(self, *args, **kwargs):
        if self.access_token_expires < utils.ms():
            self.refresh_access_token()
        return func(self, *args, **kwargs)
    return wrapper

class Token:
    def __init__(self,
        token: str,
        user_id: int,
        status: int,
        access_token: str,
        access_token_expires: int,
        refresh_token: str,
        guilds: set[int],
        type: Union[TokenTypes, int],
        added_on: int = None,
        boosts_remaining: int = None,
        raw_token: str = None,
        in_db: bool = True
    ) -> None:
        self.token = token
        self.user_id = user_id
        self.status = status
        self.access_token = access_token
        self.access_token_expires = access_token_expires
        self.refresh_token = refresh_token
        if isinstance(guilds, str): self.guilds = set(list(utils.jl(guilds)))
        elif isinstance(guilds, set): self.guilds = guilds
        elif guilds == None: self.guilds = guilds
        else: raise ValueError("guilds must be a set, str, or None")
        self.type = type if isinstance(type, TokenTypes) else TokenTypes(type)
        self.added_on = added_on
        self.boosts_remaining = boosts_remaining
        self.raw_token = raw_token
        self.in_db = in_db

        self.boost_ids = None
        self.client = oauth.http.get_client(self.token)

    def _get_ready_data(self) -> dict:
        try:
            hello = {
                "op": 2,
                "d": {
                    "token": self.token,
                    "capabilities": 16381,
                    "properties": oauth.tls.get_super_properties(as_dict=True),
                    "presence": {
                        "status": "unknown",
                        "since": 0,
                        "activities": [],
                        "afk": False
                    },
                    "compress": False,
                    "client_state": {"guild_versions":{}}
                }
            }

            ws = websocket.create_connection("wss://gateway.discord.gg/?v=9&encoding=json")
            ws.recv() # hello msg

            ws.send(utils.jd(hello))

            ready: dict = utils.jl(ws.recv())

            data = {
                'guilds': [guild['id'] for guild in ready['d']['guilds']],
                'private_channels': ready['d']['private_channels'],
            }

            ws.close()

            return data
        
        except:
            utils.log.debug(f"failed to get ready data for {self.user_id} ({self.token}) {traceback.format_exc()}")
            raise oauth.exceptions.RequestFailed

    def rescan_token(self):
        try:
            self.validate_token()
        except:
            utils.log.debug(f"failed to rescan token for {self.user_id} ({self.token}) {traceback.format_exc()}")
        else:
            if self.type.boost:
                try:
                    self.update_boost_ids()
                except:
                    utils.log.debug(f"failed to rescan token for {self.user_id} ({self.token}) {traceback.format_exc()}")
        
        self.save_to_db(False)

    @staticmethod
    def import_procedure(token: str, raw_token: str, type: TokenTypes) -> bool:
        # check if it's in the db
        user_id = utils.get_discord_id(token)

        conn, cur = db.pool.get()
        try:
            cur.execute("SELECT token FROM tokens WHERE user_id = ?;", [user_id])
            db_token = cur.fetchone()
        except:
            db.pool.release(conn, cur)
            raise oauth.exceptions.DatabaseError
        db.pool.release(conn, cur)
        
        if db_token:
            if db_token[0] == token:
                # duplicate entry
                utils.log.debug(f"duplicate entry for {user_id} ({token})")
                
                return False
            else:
                # update token
                utils.log.debug(f"updating token for {user_id}")
                conn, cur = db.pool.get()
                try:
                    cur.execute("UPDATE tokens SET token = ? WHERE user_id = ?;", [token, user_id])
                except:
                    db.pool.release(conn, cur)
                    raise oauth.exceptions.DatabaseError
                
                db.pool.release(conn, cur)
                return False
        
        # check if it's valid (whilst doing oauth)
        self = Token(
            token,
            user_id,
            status = 0,
            access_token = None,
            access_token_expires = None,
            refresh_token = None,
            guilds = None,
            type = type,
            added_on = utils.ms(),
            boosts_remaining = None,
            raw_token = raw_token,
            in_db = False
        )
        try:
            self.validate_token()
        except oauth.exceptions.InvalidToken:
            utils.log.warn(f"invalid token for {user_id} ({token})")
            raise oauth.exceptions.InvalidToken
        except oauth.exceptions.LockedToken:
            utils.log.warn(f"locked token for {user_id} ({token})")
            raise oauth.exceptions.LockedToken
        except oauth.exceptions.QuarantinedToken:
            utils.log.warn(f"quarantined token for {user_id} ({token})")
            raise oauth.exceptions.QuarantinedToken
        except oauth.exceptions.SpammerToken:
            utils.log.warn(f"spammer token for {user_id} ({token})")
            raise oauth.exceptions.SpammerToken
        except:
            utils.log.error(f"failed to do oauth for {user_id} ({token}) {traceback.format_exc()}")
            raise oauth.exceptions.TokenError

        try:
            self.join_oauth()
        except oauth.exceptions.InvalidToken:
            utils.log.warn(f"invalid token for {user_id} ({token})")
            raise oauth.exceptions.InvalidToken
        except oauth.exceptions.LockedToken:
            utils.log.warn(f"locked token for {user_id} ({token})")
            raise oauth.exceptions.LockedToken
        except:
            utils.log.error(f"failed to do oauth for {user_id} ({token}) {traceback.format_exc()}")
            raise oauth.exceptions.TokenError
        
        # calculate boosts
        if self.type.boost:
            self.update_boost_ids()
        
        # save to db
        self.save_to_db(update_guilds=False)

        return True

    def _handle_status(self, res):
        if res.status_code == 401 and 'Unauthorized' in res.text:
            self.status = 1
            raise oauth.exceptions.InvalidToken
        
        elif res.status_code == 403 and 'verify' in res.text:
            self.status = 2
            raise oauth.exceptions.LockedToken
        
        elif not str(res.status_code).startswith('2'):
            raise oauth.exceptions.RequestFailed

    @requires_access_token
    def join_server(self, guild_id: int, roles: list[int]) -> bool:
        "Returns `True` if joined, `False` if already in, raises `oauth.exceptions.FailedToJoin` if failed from status code."
        success, pending = oauth.bot.add_guild_member(guild_id, self.user_id, self.access_token, roles)
        if success:
            if pending:
                self.handle_onboarding(guild_id)
            self.guilds.add(guild_id)
            return True

        elif success is None:
            self.guilds.add(guild_id)
            return False

        else:
            if pending is True: # this happens if "Unknown User" is in the response
                self.validate_token()
            
            elif pending is False: # this happens if "Missing Permission" is in the response
                raise oauth.exceptions.BotNoPerms
            
            raise oauth.exceptions.FailedToJoin

    def validate_token(self):
        res = self.client.get("https://discord.com/api/v9/users/@me?with_analytics_token=true",
            headers = oauth.tls.headers('get', False, False, False, self.token, track=True)
        )
        utils.log.debug(f"validating token (@me) for {self.user_id}: {res.status_code} {res.text if len(res.text) < 150 else res.text[:150] + '...'}")
        self._handle_status(res)

        flags = res.json().get('flags', 0)
        if flags & (1 << 20):
            self.status = 5
            utils.log.debug(f"spammer flag found for {self.user_id}")
            raise oauth.exceptions.SpammerToken
        
        if flags & (1 << 44):
            self.status = 4
            utils.log.debug(f"quarantined flag found for {self.user_id}")
            raise oauth.exceptions.QuarantinedToken
        
        employee_channel_id = None

        utils.log.debug(f"fetching gateway ready data for {self.user_id}")
        ready_data = self._get_ready_data()
        self.guilds = set(ready_data['guilds'])
        
        for channel in ready_data['private_channels']:
            if "643945264868098049" in channel['recipient_ids']: # discord employee ID
                employee_channel_id = channel['id']
                break

        if employee_channel_id:
            res = self.client.get(f"https://discord.com/api/v9/channels/{employee_channel_id}/messages?limit=50",
                headers = oauth.tls.headers('get', True, True, True, self.token)
            )
            utils.log.debug(f"fetching alert channel for {self.user_id}: {res.status_code} {res.text if len(res.text) < 150 else res.text[:150] + '...'}")
            self._handle_status(res)

            for message in res.json():
                if "articles/6461420677527" in message.get('content', ''): # "You may click here to learn more (https://support.discord.com/hc/en-us/articles/6461420677527)."
                    self.status = 4
                    utils.log.debug(f"found 'articles/6461420677527' quarantined substring for {self.user_id}")
                    raise oauth.exceptions.QuarantinedToken
        
        return True

    def join_oauth(self):
        res = self.client.post(f"https://discord.com/api/v9/oauth2/authorize",
            json={
                "authorize": True,
                "intergration_type": 0,
                "permissions": "0"
            },
            params={
                'client_id': config().discord_app.client_id,
                'response_type': 'code',
                'redirect_uri': config().discord_app.plain_redirect_uri,
                'scope': 'identify guilds guilds.join'
            },
            headers=oauth.tls.headers('post', True, True, True, self.token, oauth.oauth_link.replace('+bot', 'guilds.join'))
        )
        utils.log.debug(f"authorizing oauth for {self.user_id}: {res.status_code} {res.text}")
        self._handle_status(res)

        oauth_data = oauth.bot.handle_oauth_code(res.json()['location'].split('code=')[1])
        if oauth_data:
            self.access_token = oauth_data['access_token']
            self.refresh_token = oauth_data['refresh_token']
            self.access_token_expires = oauth_data['expires_in']
        else:
            raise oauth.exceptions.BotOauthError

    def refresh_access_token(self):
        oauth_data = oauth.bot.refresh_access_token(self.refresh_token)
        if oauth_data:
            self.access_token = oauth_data['access_token']
            self.refresh_token = oauth_data['refresh_token']
            self.access_token_expires = oauth_data['expires_in']
        else:
            raise oauth.exceptions.BotOauthError
    
    def update_boost_ids(self):
        if not self.type.boost:
            return
    
        res = self.client.get("https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots",
            headers = oauth.tls.headers('get', True, True, True, self.token, f"https://discord.com/channels/@me")
        )
        utils.log.debug(f"getting boost ids for {self.user_id}: {res.status_code} {res.text}")
        self._handle_status(res)
        
        boosts: list[str] = [boost['id'] for boost in res.json() if boost.get('cooldown_ends_at') is None]
        self.boosts_remaining = len(boosts)
        self.boost_ids = boosts

    @requires_access_token
    def update_guilds(self):
        guilds = oauth.bot.get_guild_ids_of_user(self.access_token)
        if guilds != None:
            self.guilds = set(guilds)
        else:
            raise oauth.exceptions.RequestFailed

    def boost_server(self, guild_id: Union[str, int], boost_id: str):
        res = self.client.put(f"https://discord.com/api/v9/guilds/{guild_id}/premium/subscriptions",
            headers = oauth.tls.headers('put', True, True, True, self.token, f"https://discord.com/channels/@me"),
            json = {
                "user_premium_guild_subscription_slot_ids": [str(boost_id)]
            }
        )
        utils.log.debug(f"boosting {guild_id} for {self.user_id}: {res.status_code} {res.text}")
        self._handle_status(res)

        if res.status_code == 201:
            self.boosts_remaining -= 1
            return True

    def handle_onboarding(self, guild_id:int):
        onboarding = oauth.bot.get_onboarding(guild_id)
        if onboarding:
            if onboarding['enabled']:
                seen_time = int(time.time())

                payload = {
                    "onboarding_responses": [],
                    "onboarding_prompts_seen": {},
                    "onboarding_responses_seen": {}
                }

                for prompt in onboarding['prompts']:
                    payload['onboarding_prompts_seen'][prompt['id']] = seen_time
                    if prompt['single_select']:
                        payload["onboarding_responses"].append(prompt['options'][0]['id'])
                        payload["onboarding_responses_seen"][prompt['options'][0]['id']] = seen_time
                    else:
                        try:
                            for option in prompt['options']:
                                payload["onboarding_responses"].append(option['id'])
                                payload["onboarding_responses_seen"][option['id']] = seen_time
                        except:
                            pass

                res = self.client.put(f"https://discord.com/api/v9/guilds/{guild_id}/onboarding-responses",
                    headers = oauth.tls.headers('put', True, True, True, self.token, f"https://discord.com/channels/{guild_id}/onboarding"),
                    json = payload
                )
                utils.log.debug(f"putting onboarding in {guild_id} for {self.user_id}: {res.status_code} {res.text}")

                if res.status_code == 200:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def save_to_db(self, update_guilds:bool=True):
        if update_guilds:
            try:
                self.update_guilds()
            except:
                utils.log.debug(f"failed to update guilds for {self.user_id} ({self.token}) {traceback.format_exc()}")

        conn, cur = db.pool.get()
        if self.in_db:
            utils.log.debug(f"updating token for {self.user_id}")
            sql = """UPDATE tokens
                SET token = ?, status = ?, access_token = ?, access_expire = ?, refresh_token = ?, guild_count = ?, type = ?, guilds = ?, boosts_remaining = ?, raw_token = ?
                WHERE user_id = ?;"""
            args = [self.token, self.status, self.access_token, self.access_token_expires, self.refresh_token, len(self.guilds), self.type.key, utils.jd(list(self.guilds)), self.boosts_remaining, self.raw_token,
                    self.user_id]
        
        else:
            utils.log.debug(f"inserting token for {self.user_id}")
            sql = """INSERT INTO tokens (token, user_id, status, access_token, access_expire, refresh_token, guild_count, type, guilds, added_on, boosts_remaining, raw_token)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
            args = [self.token, self.user_id, self.status, self.access_token, self.access_token_expires, self.refresh_token, len(self.guilds), self.type.key, utils.jd(list(self.guilds)), self.added_on, self.boosts_remaining, self.raw_token]
        
        try:
            cur.execute(sql, args)
        except:
            db.pool.release(conn, cur)
            raise oauth.exceptions.DatabaseError
        
        db.pool.release(conn, cur)

        self.in_db = True


def handle_expired_tokens(user_ids: list[int]):
    conn, cur = db.pool.get()
    
    utils.log.debug(f"updating expired tokens: {user_ids}")
    
    try:
        cur.execute(
            """UPDATE tokens
            SET status = 3
            WHERE user_id IN (?);""",
            [user_ids]
        )
    except:
        utils.log.warn(f"failed to update expired tokens: {traceback.format_exc()}")
        
    db.pool.release(conn, cur)


def search(type:TokenTypes, guild_id:Union[int, None]) -> list[Token]:
    # search for tokens that arent in this server
    conn, cur = db.pool.get()
    try:
        if guild_id:
            sql = """SELECT token, user_id, status, access_token, access_expire, refresh_token, guilds, type, added_on, boosts_remaining, raw_token FROM tokens
                WHERE status = 0 AND type = ? AND guilds NOT LIKE ? AND (boosts_remaining = 1 OR boosts_remaining = 2 OR boosts_remaining IS NULL) AND guild_count != 100;"""
            args = [type.key, f"%{guild_id}%"]
        else:
            sql = """SELECT token, user_id, status, access_token, access_expire, refresh_token, guilds, type, added_on, boosts_remaining, raw_token FROM tokens
                WHERE status = 0 AND type = ? AND (boosts_remaining = 1 OR boosts_remaining = 2 OR boosts_remaining IS NULL) AND guild_count != 100;"""
            args = [type.key]

        cur.execute(sql, args)
        stock_available: list[tuple] = cur.fetchall()
    except:
        db.pool.release(conn, cur)
        raise oauth.exceptions.DatabaseError
    
    db.pool.release(conn, cur)
    
    expired_tokens = []
    current_time = utils.ms()
    max_age = current_time - getattr(config().max_age, type.type_str, current_time+1)

    if max_age != -1:
        for token in stock_available:
            if token[1] + max_age < current_time:
                expired_tokens.append(token[1])
    
    if expired_tokens:
        handle_expired_tokens(expired_tokens)

    random.shuffle(stock_available)

    return [Token(*token) for token in stock_available if token[1] not in expired_tokens]


def pre_check_search(type:TokenTypes, quantity: int, guild_id:int) -> bool:
    # fetch all tokens that arent in this server and of this type
    conn, cur = db.pool.get()
    try:
        cur.execute(
            """SELECT user_id, added_on, boosts_remaining FROM tokens
            WHERE status = 0 AND type = ? AND guilds NOT LIKE ? AND (boosts_remaining = 1 OR boosts_remaining = 2 OR boosts_remaining IS NULL) AND guild_count != 100;""",
            [type.key, f"%{guild_id}%"]
        )
        stock: list[tuple] = cur.fetchall()
    except:
        db.pool.release(conn, cur)
        raise oauth.exceptions.DatabaseError
    
    db.pool.release(conn, cur)

    # checks if the tokens haven't hit max age
    stock_available = 0
    expired_tokens = []
    current_time = utils.ms()
    max_age = current_time - getattr(config().max_age, type.type_str, current_time+1)

    if max_age == -1:
        stock_available = len(stock)
    else:
        for token in stock:
            if token[1] + max_age < current_time:
                expired_tokens.append(token[0])
            else:
                if type.boost:
                    stock_available += token[2]
                else:
                    stock_available += 1

    if expired_tokens:
        handle_expired_tokens(expired_tokens)

    if stock_available >= quantity:
        return True
    else:
        return False


def get_stock_quantity(type:TokenTypes) -> int:
    # fetch all tokens that arent in this server and of this type
    conn, cur = db.pool.get()
    try:
        cur.execute(
            """SELECT user_id, added_on, boosts_remaining FROM tokens
            WHERE status = 0 AND type = ? AND (boosts_remaining = 1 OR boosts_remaining = 2 OR boosts_remaining IS NULL) AND guild_count != 100;""",
            [type.key]
        )
        stock: list[tuple] = cur.fetchall()
    except:
        db.pool.release(conn, cur)
        raise oauth.exceptions.DatabaseError
    
    db.pool.release(conn, cur)

    # checks if the tokens haven't hit max age
    stock_available = 0
    expired_tokens = []
    current_time = utils.ms()
    max_age = current_time - getattr(config().max_age, type.type_str, current_time+1)

    
    for token in stock:
        if max_age != -1:
            if token[1] + max_age < current_time:
                expired_tokens.append(token[0])
                continue

        if type.boost:
            stock_available += token[2]
        else:
            stock_available += 1

    if expired_tokens:
        handle_expired_tokens(expired_tokens)

    return stock_available


def import_tokens(raw_data: list[str], type:TokenTypes):
    success = 0
    duplicate = 0
    for raw_token in raw_data:
        utils.log.debug(f"importing {raw_token}")
        raw_token = raw_token.strip(' ')
        
        if ':' in raw_token:
            token = raw_token.split(':')[-1]
        else:
            token = raw_token
        
        try:
            if Token.import_procedure(token, raw_token, type):
                success += 1
            else:
                duplicate += 1
        except:
            utils.log.error(f"failed to import {raw_token}: {traceback.format_exc()}")
    
    utils.log.info(f"imported {success}/{len(raw_data)} tokens successfully ({duplicate} duplicate(s))")


def rescan_tokens(tokens: list[str]):
    utils.log.debug(f"rescanning {len(tokens)} token(s)")
    for token in tokens:
        user_id = utils.get_discord_id(token)
        conn, cur = db.pool.get()
        try:
            cur.execute(
                '''SELECT token, user_id, status, access_token, access_expire, refresh_token, guilds, type, added_on, boosts_remaining, raw_token
                FROM tokens WHERE user_id = ?;''',
                [user_id]
            )
            data = cur.fetchone()
        except:
            db.pool.release(conn, cur)
            raise oauth.exceptions.DatabaseError
        
        db.pool.release(conn, cur)

        if data:
            utils.log.debug(f"rescanning {token}")
            Token(*data).rescan_token()
        else:
            utils.log.debug(f"token {token} not found in db")
