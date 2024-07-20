import httpx
from dataclasses import dataclass
from typing import Union
import utils
import traceback

from web.api.auth import CaptchaPayload, authorise_jwt, generate_jwt
from config import config



client = httpx.Client(http2=True)

# expected_hostname = "deeeez.chasa.wtf"

@dataclass
class TurnstileResponse:
    passed: bool
    reason: str
    interactive: Union[bool, None]
    raw_data: Union[dict, str]


class CaptchaJWTInvalid(Exception):
    pass


class Captcha:
    def __init__(self, ip, _hashed=False, _cdata=None) -> None:
        self.cdata = utils.rand_str_hex(64) if not _cdata else _cdata
        self._ip = utils.sha256(ip) if not _hashed else ip
        
        self.created_at = utils.ms()
        self.site_key = config().turnstile.sitekey
        self.expires_at = self.created_at + config().turnstile.jwt_expire

    @staticmethod
    def from_jwt(payload: Union[str, CaptchaPayload]):
        if isinstance(payload, str) or not payload.validated:
            payload = authorise_jwt(payload, 1)

            if not payload:
                raise CaptchaJWTInvalid

        if not payload.validated:
            raise CaptchaJWTInvalid
        
        return Captcha(payload.z, True, payload.x)

    def to_jwt(self) -> str:
        return generate_jwt(
            CaptchaPayload(
                self.cdata,
                self._ip,
                self.created_at,
                self.expires_at
            )
        )

    def check(
        self,
        result: str,
        ip: str = None
    ) -> TurnstileResponse:    
        reasons = []
        
        data = {
            'secret': config().turnstile.secret,
            'sitekey': config().turnstile.sitekey,
            'response': result
        }
        if ip:
            data['remoteip'] = ip

        req = {}
        
        if ip and self._ip != utils.sha256(ip):
            reasons.append('ip-mismatch')
        else:
            try:
                req: dict = client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    json = data
                ).json()
        
                # {
                #   'success': True,
                #   'error-codes': [],
                #   'challenge_ts': '2023-11-17T16:55:22.427Z',
                #   'hostname': '***',
                #   'action': '',
                #   'cdata': 'cKrTdjGjd4MIG2zf59rKgCASqCOc6Ruex0v6W47LQ7O90sOXUD05HbZyfDeYBeNZ', 
                #   'metadata': {'interactive': False}
                # }

            except:
                return TurnstileResponse(
                    False,
                    'req_fail',
                    False,
                    traceback.format_exc()
                )
            
            else:
                if not req['success']:
                    reasons: list = req['error-codes']
                else:
                    if self.cdata:
                        if req.get('cdata') != self.cdata:
                            reasons.append('bad-cdata')
                    
                    if utils.ms() > self.expires_at:
                        reasons.append('expired-jwt')
                    
                    #if req.get('hostname', expected_hostname) != expected_hostname:
                    #    reasons.append('bad-hostname')
        
        if reasons:
            utils.log.debug(f"user on {ip} failed turnstile failed: {reasons}")

        return TurnstileResponse(
            False if reasons else True,
            ', '.join(reasons),
            req.get('metadata', {}).get('metadata'),
            req
        )
