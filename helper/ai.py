import g4f
import time
import traceback
import luxurynitro
import utils
import httpx
import re
import json

g4f.debug.logging = True

luxury = luxurynitro.Client('api_5***')
sellix_apikey = 'pDMq6***'
sellix_products_ids = {
    "paypal": "64c98b347fce7",
    "other": "641b388e1bf43"
}

sources_re = re.compile(r'\[[0-9]*\]: http')
sources2_re = re.compile(r'\[\^[0-9]{1,}\^\]\[[0-9]{1,}\]')

f = open('prompt.txt')
prompt_template = f.read()
f.close()

f = open('proxy.txt')
proxy = f.read()
f.close()

if '.' not in proxy:
    proxy = None

real_time_template = """Currently, credits are priced differently for each payment method:
Paypal: {} per credit + {} fee (the fee is the same despite the number of credits bought)
Cashapp: {} per credit
Crypto ({}): {} per credit + network fee
These prices are 100% accurate and are updated automatically for you.
All prices are in USD (United States Dollars).
Other payment methods may be available, but at staff's discretion.
If a user would like to use a different crypto currency, tell them to use an exchange like https://sideshift.ai/ or https://changenow.io/, and to set the destination address as the address given to them by Sellix, or to ping a staff member for help.
If a user would like to pay via Cashapp, tell them to send money to "$dylankeezer4" and to ping a staff member. Cashapp cannot be purchased automatically on the website.
When calculating prices, attempt to calculate it yourself, however always ask the user to check themselves on the website.{}

Here is some info about the current queue (this is 100% accurate, and is updated automatically):
- The length of the queue is {} gifts long, across {} order(s).
- The ETA of when the queue will be completely empty is {}.
- The estimated time it would take for a user to get nitro, if they join the queue right now, is {}.
- The last nitro someone received was {}, and it was received {} ago. A{} received it.
- There has been {} nitro claims in the last 24 hours, {} boost, {} basic, {} classic (monthly and yearly are combined here).
- If the user needs to see specific information about the queue, redirect them to the #queue channel.
- All times are estimated, and over-inflated. Users most likely won't have to wait this long. Please make this clear to the user.

Here is some general stats about the service (100% accurate info, auto-updated):
- The sniper is watching {} servers across {} discord accounts (or alts).
- We've sniped {} nitro gifts since we started counting in June 2022.
- You (roughly) have a {}% chance of getting Nitro Boost compared to Nitro Classic or Nitro Basic (based off the last 25 orders)."""

category_template = """This ticket was created under the category: {}
Use the category as a hint for your response.
If this is the user's first question, it is likely the user's question will be about this topic, so feel free to make assumptions straight away.
For example, if the ticket category is "Luxify Sniper" and the question is "how much does it cost?", you should answer with the price of the Luxify Sniper, not how much credits cost.

Users can close the ticket by using the button at the top of the channel, or by using /close."""

channels_template = """

When you mention a specific channel, always use these special values instead, including in non-english, no matter where it's used:
"#queue" to "<#{}>"
"#claims" to "<#{}>"
"#sellix-orders" to "<#{}>"
"#sellix-reviews" to "<#{}>"
"#giveaways" to "<#{}>"
"""

previous_messages_template = """
Here is a list of previous messages the user has asked (each line is a different message):{}
These may be relevant to the conversation, so keep these in mind whilst replying.
The most recent (and the most important) is at the bottom of the list.
If a user refers to "it", then its likely that one of these questions could hint towards what "it" is."""

no_previous_msgs = "This user hasn't sent any messages in this ticket before, so use the ticket category for hints."

general_template = """This message is not in a ticket, it is a question asked in general. Do not mention anything about opening or closing tickets."""

real_time_data = {
    "paypal": "0.00",
    "paypal_fee": "0.00",
    "cashapp": "0.00",
    "crypto_types": "",
    "crypto": "0.00",
    "discounts": "",
    
    "queue_len": "0",
    "order_len": "0",
    "queue_eta_complete": "0s",
    "last_order_eta": "0s",
    "last_nitro_type": "",
    "last_nitro_time": "",
    "last_nitro_user": "",
    "24hr_total": "0",
    "24hr_boost": "0",
    "24hr_basic": "0",
    "24hr_classic": "0",
    
    "sniper_servers": "0",
    "sniper_alts": "0",
    "sniper_gifts": "0",
    "sniper_chance": "0",
}

def update_real_time_data():
    global real_time_data
    print("Started real_time thread.")
    while True:
        try:
            user_data = luxury.get_user()
            real_time_data["sniper_alts"] = str(user_data.stats.alts)
            real_time_data["sniper_chance"] = str(user_data.stats.boost_chance)
            real_time_data["sniper_gifts"] = str(user_data.stats.total_claims)
            real_time_data["sniper_servers"] = str(user_data.stats.servers)
        except:
            print("[real_time] Error on luxury get_user():")
            traceback.print_exc()

        try:
            queue_data = luxury.get_queue()
            real_time_data["queue_len"] = str(queue_data.length)
            real_time_data["order_len"] = str(len(queue_data.queue))
            real_time_data["queue_eta_complete"] = utils.convertHMS(queue_data.eta.completed)
            real_time_data["last_order_eta"] = utils.convertHMS(queue_data.queue[-1].eta.completed + queue_data.eta.next_gift)
            real_time_data["last_nitro_type"] = queue_data.recent[0].nitro_type._type
            real_time_data["last_nitro_time"] = utils.convertHMS(int(time.time()) - queue_data.recent[0].timestamp)
            if queue_data.recent[0].user.id == -1:
                real_time_data["last_nitro_time"] = 'n anonymous user'
            else:
                real_time_data["last_nitro_time"] = f' user with the username "{queue_data.recent[0].user.display_name}"'

            tmp = {
                "24hr_total": "0",
                "24hr_boost": "0",
                "24hr_basic": "0",
                "24hr_classic": "0",
            }
            current_time = int(time.time())
            for claim in queue_data.recent:
                if claim.timestamp < current_time - 86400:
                    break

                tmp["24hr_total"] = str(int(tmp["24hr_total"]) + 1)
                if claim.nitro_type.boost:
                    tmp["24hr_boost"] = str(int(tmp["24hr_boost"]) + 1)
                elif claim.nitro_type.basic:
                    tmp["24hr_basic"] = str(int(tmp["24hr_basic"]) + 1)
                elif claim.nitro_type.classic:
                    tmp["24hr_classic"] = str(int(tmp["24hr_classic"]) + 1)
            
            for key, value in tmp.items():
                real_time_data[key] = value

        except:
            print("[real_time] Error on luxury get_queue():")
            traceback.print_exc()

        try:
            res = httpx.get("https://api-internal.sellix.io/v1/shops/LuxuryBoosts")
            res.raise_for_status()
            sellix_data = res.json()['data']['products']
            
            tmp = ""
            for product in sellix_data:
                if product['uniqid'] == sellix_products_ids["paypal"]:
                    real_time_data["paypal"] = product['price_display']
                    if product['payment_gateways_fees'][0]['active_type'] == "FIXED":
                        real_time_data["paypal_fee"] = str(product['payment_gateways_fees'][0]['fixed_amount'])
                    else:
                        real_time_data["paypal_fee"] = "0.00"
                
                elif product['uniqid'] == sellix_products_ids['other']:
                    real_time_data["cashapp"] = product['price_display']
                    real_time_data["crypto"] = product['price_display']
                    real_time_data["crypto_types"] = product['gateways']

                    for discount in json.loads(product['volume_discounts'])['volume_discounts']:
                        if discount['type'] == 'PERCENTAGE':
                            tmp += f'\nThere is currently a {discount["value"]}% discount (applied automatically) when you purchase {discount["quantity"]} or more credits.'
                        elif discount['type'] == 'FIXED':
                            tmp += f'\nThere is currently a {discount["value"]} USD off discount (applied automatically) when you purchase {discount["quantity"]} or more credits.'
            
            real_time_data["discounts"] = tmp

        except:
            print("[real_time] Error on sellix api:")
            traceback.print_exc()

        time.sleep(5)

def format_old_msgs(old_msgs: list, category:str=None):
    data = previous_messages_template.format(''.join(f"\n- {x}" for x in old_msgs)) if old_msgs else ''
    if not old_msgs and category:
        data += '\n\n' + no_previous_msgs
    return data

async def reply(question:str, channels:list, category:str=None, old_msgs:list=[]) -> str:
    category_data = category_template.format(category) if category else general_template

    content = prompt_template.format(
        real_time_template.format(*list(real_time_data.values())) + "\n\n" + category_data + channels_template.format(*channels) + format_old_msgs(old_msgs, category)
    ) + question

    response = None
    for _ in range(7):
        try:
            response = await g4f.ChatCompletion.create_async(
                model=g4f.Model(
                    name          = 'gpt-4',
                    base_provider = 'openai',
                    best_provider = g4f.Provider.RetryProvider([
                        g4f.Provider.Bing,g4f.Provider.GeekGpt,g4f.Provider.GeekGpt,g4f.Provider.GeekGpt,g4f.Provider.GeekGpt
                    ])
                ),
                messages=[
                    {"role": "user", "content": content}
                ],
                proxy=proxy,
                timeout=120
            )
        except:
            print(f'[reply] error fetching model ignored:')
            traceback.print_exc()
            continue
        else:
            break
    
    if response:
        formatted = []
        for line in response.split('\n'):
            if sources_re.findall(line):
                continue

            if line.startswith('>') and len(line) < 5:
                continue

            line = sources2_re.sub("", line)

            formatted.append(line)

        return '\n'.join(formatted)
    else:
        raise Exception