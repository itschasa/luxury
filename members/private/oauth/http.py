import httpx
import time
import tls_client

from oauth.exceptions import RetryTimeout
from oauth import tls



class HTTP():
    def __init__(self, type: str, timeout:int=25, max_retries:int=5) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        
        if type == 'bot':
            self._http = httpx.Client(http2=True, base_url="https://discord.com/api/v9")
        else:
            self.max_retries = 3
            self._http = tls_client.Session(client_identifier=tls.client_identifier, random_tls_extension_order=True)

    def _exec_retries(self, method, *args, **kwargs) -> httpx.Response:
        errors = []
        for _ in range(self.max_retries):
            try:
                return method(*args, **kwargs)
            except httpx.HTTPError as e:
                errors.append(e)
        raise RetryTimeout(f"Max retries done: {errors[-1]}", errors)
    
    def _req(self, method, *args, **kwargs) -> httpx.Response:
        while True:
            res = self._exec_retries(method, *args, **kwargs)
            if res.status_code == 429:
                time.sleep(float(res.headers['X-Ratelimit-Reset-After']) + 0.1)
            else:
                if res.status_code >= 500:
                    continue
                else:
                    return res

    def get(self, *args, **kwargs) -> httpx.Response:
        return self._req(self._http.get, *args, **kwargs)

    def post(self, *args, **kwargs) -> httpx.Response:
        return self._req(self._http.post, *args, **kwargs)
    
    def put(self, *args, **kwargs) -> httpx.Response:
        return self._req(self._http.put, *args, **kwargs)
    
    def delete(self, *args, **kwargs) -> httpx.Response:
        return self._req(self._http.delete, *args, **kwargs)
    

client_token_dict: dict[str, HTTP] = {'bot': HTTP('bot')}
def get_client(token: str):
    if token not in client_token_dict:
        client_token_dict[token] = HTTP('user')

    return client_token_dict[token]
