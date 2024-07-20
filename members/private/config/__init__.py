import yaml
from dataclasses import dataclass
import dacite



@dataclass
class discord_app:
    token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    plain_redirect_uri: str


@dataclass
class sellix:
    secret_key: str
    balance_product_id: str


@dataclass
class prices:
    online: int
    offline: int
    boost_1month: int
    boost_3month: int


@dataclass
class max_age:
    boost_1month: int
    boost_3month: int


@dataclass
class turnstile:
    sitekey: str
    secret: str
    jwt_expire: int


@dataclass
class jwt:
    secret: str
    algor: str


@dataclass
class email:
    address: str
    password: str
    jwt_expire: int


@dataclass
class Config:
    discord_app: discord_app
    sellix: sellix
    admins: list[int]
    prices: prices
    max_age: max_age
    turnstile: turnstile
    jwt: jwt
    email: email
    snowflake_epoch: int
    auth_jwt_expire: int
    forgot_jwt_expire: int


cache: Config = None

def config(force=False) -> Config:
    global cache
    if force or not cache:
        data = yaml.safe_load(open("config/config.yml"))
        cache = dacite.from_dict(Config, data)
    return cache
