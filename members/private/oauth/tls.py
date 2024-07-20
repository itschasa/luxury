import httpx
import re
import traceback
import base64

import utils



super_properties_base = {"os":"Windows","browser":"Chrome","device":"","system_locale":"en-US","browser_user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36","browser_version":"121.0.0.0","os_version":"10","referrer":"","referring_domain":"","referrer_current":"","referring_domain_current":"","release_channel":"stable","client_build_number":262828,"client_event_source":None}
super_properties: str = None
super_properties_num: int = None

client_identifier = "chrome_117"
x_track = "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMS4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIxLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjk5OTksImNsaWVudF9ldmVudF9zb3VyY2UiOm51bGx9"

client_build_number: int = None
client_build_number_update: int = 0


def get_client_build_number():
    global client_build_number, client_build_number_update
    if client_build_number_update + 600000 < utils.ms() or client_build_number is None:
        try:
            login_page_request = httpx.get('https://discord.com/login', headers={"Accept-Encoding": "identity"})
            login_page = login_page_request.text
            build_url = 'https://discord.com/assets/' + re.compile(r'assets/(sentry\.\w+)\.js').findall(login_page)[0] + '.js'
            build_request = httpx.get(build_url, headers={"Accept-Encoding": "identity"})
            build_nums = re.findall(r'buildNumber\D+(\d+)"', build_request.text)
            client_build_number = int(build_nums[0])
    
        except:
            utils.log.error(f"failed to get client build number: {traceback.format_exc()}")
            if client_build_number is None:
                client_build_number = 262828
        
        client_build_number_update = utils.ms()
    
    return client_build_number


def get_super_properties(as_dict=False):
    global super_properties, super_properties_num, super_properties_base
    if super_properties_num is None or super_properties_num != client_build_number:
        super_properties_base["client_build_number"] = get_client_build_number()
        super_properties = base64.b64encode(utils.jd(super_properties_base).encode()).decode()
        super_properties_num = client_build_number

    if as_dict:
        return super_properties_base
    
    return super_properties


def headers(
    method: str,
    superprop     = False,
    debugoptions  = False,
    discordlocale = False,
    token         = False,
    referer       = "https://discord.com/",
    context       = False,
    track         = False
):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Sec-Ch-Ua": f'"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?0",
        'Sec-Ch-Ua-Platform': '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    if not referer:
        del headers["Referer"]
    
    if method != "get":
        headers["Content-Type"] = "application/json"
        headers["Origin"] = "https://discord.com"

    if token:
        headers["Authorization"] = token
    if debugoptions:
        headers["X-Debug-Options"] = "bugReporterEnabled"
    if discordlocale:
        headers["X-Discord-Locale"] = "en-US"
    if superprop:
        headers["X-Super-Properties"] = get_super_properties()
    if context:
        headers["X-Context-Properties"] = context
    if track:
        headers["X-Track"] = x_track

    return headers
