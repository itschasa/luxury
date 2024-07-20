import utils
import oauth
from config import config



client = oauth.http.get_client('bot')
oauth2_header = "Bearer {}"
bot_headers = {"Authorization": "Bot {}".format(config().discord_app.token)}


def check_for_guild(guild_id: int) -> bool:
    res = client.get(f"/guilds/{guild_id}", headers=bot_headers)
    utils.log.debug(f"fetching guild {guild_id}: {res.status_code} {res.text}")
    if res.status_code == 200:
        return True
    else:
        return False


on_boarding_cache: dict[int, tuple[int, dict]] = {}
def get_onboarding(guild_id: int) -> dict:
    if guild_id in on_boarding_cache and utils.ms() - on_boarding_cache[guild_id][0] < 300000: # 5 mins cache
        utils.log.debug(f"found onboarding for {guild_id} in cache ({(utils.ms() - on_boarding_cache[guild_id][0])/1000}s old)")
        return on_boarding_cache[guild_id][1]
    
    res = client.get(f"/guilds/{guild_id}/onboarding", headers=bot_headers)
    utils.log.debug(f"fetching onboarding in {guild_id}: {res.status_code} {res.text}")
    if res.status_code == 200:
        on_boarding_cache[guild_id] = (utils.ms(), res.json())
        return on_boarding_cache[guild_id][1]
    
    else:
        return None


def add_guild_member(guild_id: int, user_id: int, access_token: str, roles: list[int]) -> tuple[bool, bool]:
    "returns `(success, pending)`. when `success=None`, then user is already in guild"
    
    res = client.put(f'/guilds/{guild_id}/members/{user_id}',
        json={
            'access_token': access_token,
            'roles': roles
        },
        headers=bot_headers
    )
    utils.log.debug(f"adding {user_id} to {guild_id}: {res.status_code} {res.text}")

    if res.status_code == 201:
        if res.json().get('pending'):
            return True, True
        return True, False
    
    elif res.status_code == 204:
        # user already in guild
        return None, None
    
    else:
        if 'Unknown User' in res.text:
            return False, True
        elif 'Missing Permission' in res.text:
            return False, False
        return False, None


def get_role_ids(guild_id: int) -> list[int]:
    res = client.get(f"/guilds/{guild_id}/roles", headers=bot_headers)
    utils.log.debug(f"fetching roles in {guild_id}: {res.status_code} {res.text}")
    if res.status_code == 200:
        return [int(role['id']) for role in res.json()]
    else:
        return None


def get_guild_ids_of_user(access_token: str):
    res = client.get("/users/@me/guilds", headers={"Authorization": oauth2_header.format(access_token)})
    utils.log.debug(f"fetching guilds of user: {res.status_code} {res.text if len(res.text) < 150 else res.text[:150] + '...'}")
    if res.status_code == 200:
        return [int(guild['id']) for guild in res.json()]
    else:
        return None


def handle_oauth_code(code: str):
    start_time = utils.ms()
    res = client.post("/oauth2/token",
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': config().discord_app.plain_redirect_uri
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(config().discord_app.client_id, config().discord_app.client_secret)
    )
    utils.log.debug(f"handling oauth code: {res.status_code} {res.text}")

    if res.status_code == 200:
        return {
            'access_token': str(res.json()['access_token']),
            'refresh_token': str(res.json()['refresh_token']),
            'expires_in': int(res.json()['expires_in']) * 1000 + start_time
        }
    else:
        return None
    

def refresh_access_token(refresh_token: str):
    start_time = utils.ms()
    res = client.post("/oauth2/token",
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(config().discord_app.client_id, config().discord_app.client_secret)
    )
    utils.log.debug(f"refreshing access token: {res.status_code} {res.text}")

    if res.status_code == 200:
        return {
            'access_token': str(res.json()['access_token']),
            'refresh_token': str(res.json()['refresh_token']),
            'expires_in': int(res.json()['expires_in']) * 1000 + start_time
        }
    else:
        return None

def leave_guild(guild_id: int):
    res = client.delete(f"/users/@me/guilds/{guild_id}", headers=bot_headers)
    utils.log.debug(f"leaving guild {guild_id}: {res.status_code} {res.text}")
    return res.status_code == 204
