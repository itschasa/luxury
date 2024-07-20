import ai
import threading
import discord
import re
import json
import asyncio
import time

client = discord.Client(intents=discord.Intents.all())

f = open("token.txt", 'r')
bot_token = f.read()
f.close()

f = open('data.json', 'r', encoding='utf-8')
const_data: dict = json.loads(f.read())
f.close()

save_data_lock = threading.Lock()
def save_data():
    with save_data_lock:
        f = open('data.json', 'w', encoding='utf-8')
        f.write(json.dumps(const_data, indent=4))
        f.close()

welcome_msg = """**Hello! My name is Luxury Helper, an AI assistant for Luxury Services, and I'm here to assist you with any questions or problems you have.**

Please keep in mind that I'm an AI, not a human:
- Whilst I am provided with real-time data, __my answers might be inaccurate__.
- I'm only aware of the last 10 questions you asked.
- __I can read and speak in any language.__
- If you want me to stop replying, just say "@LuxuryHelper stop".
- __I'll wait until you finish typing before answering, so please be patient.__

**With that out the way, how can I help you today?**"""

channel_ids = {
    "queue": "",
    "claims": "",
    "orders": "",
    "reviews": "",
    "giveaways": "",
}

threading.Thread(target=ai.update_real_time_data, daemon=True).start()

@client.event
async def on_ready():
    print("Discord bot ready!")
    
    global channel_ids
    for guild in client.guilds:
        if "Luxury" in guild.name:
            for channel in guild.channels:
                if channel.type.name == 'text':
                    channel_name = re.sub(r'\W+', '', channel.name)
                    if channel_name == 'queue':
                        channel_ids["queue"] = str(channel.id)
                        print(f"Found Queue Channel ID: #{channel.name}")
                    
                    elif channel_name == 'claims':
                        channel_ids["claims"] = str(channel.id)
                        print(f"Found Claims Channel ID: #{channel.name}")

                    elif "sellix" in channel_name and "order" in channel_name:
                        channel_ids["orders"] = str(channel.id)
                        print(f"Found Orders Channel ID: #{channel.name}")

                    elif "sellix" in channel_name and ("feedback" in channel_name or "review" in channel_name):
                        channel_ids["reviews"] = str(channel.id)
                        print(f"Found Reviews Channel ID: #{channel.name}")
                    
                    elif "giveaways" in channel_name and "customer" not in channel_name:
                        channel_ids["giveaways"] = str(channel.id)
                        print(f"Found Giveaways Channel ID: #{channel.name}")

    await client.change_presence(status=discord.Status.online, activity=discord.Game("ice hockey or smth idk"))

#@client.event
#async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
#    if payload.cached_message:
#        print('yes')
#        message = payload.cached_message
#    else:
#        channel = client.get_channel(payload.channel_id)
#        if isinstance(channel, discord.TextChannel):
#            message = await channel.fetch_message(payload.message_id)
#        else:
#            return
#    
#    if "ticket" in message.channel.category.name.lower():
#        print(message.embeds)
#        if len(message.embeds) == 1:
#            print(message.embeds[0].description)
#            if ", this is your ticket" in message.embeds[0].description: # new ticket
#                if not const_data['tickets'].get(str(message.channel.id)):
#                    category = message.embeds[0].description.split('\n')[0].split("** ")[1].replace("Nitro Sniper", "Luxify Sniper")
#                    user_id = message.embeds[0].description.split('<@')[1].split('>')[0]
#                    
#                    await message.channel.send(welcome_msg)
#
#                    const_data["tickets"][str(message.channel.id)] = {
#                        "category": category,
#                        "author_id": int(user_id),
#                        "listen": True,
#                        "past_messages": []
#                    }
#                    save_data()

@client.event
async def on_message_edit(_, after: discord.Message):
    global const_data
    if "ticket" in after.channel.category.name.lower():
        if len(after.embeds) == 1:
            if ", this is your ticket" in after.embeds[0].description: # new ticket
                if not const_data['tickets'].get(str(after.channel.id)):
                    category = after.embeds[0].description.split('\n')[0].split("** ")[1].replace("Nitro Sniper", "Luxify Sniper")
                    user_id = after.embeds[0].description.split('<@')[1].split('>')[0]
                    
                    await after.channel.send(welcome_msg)

                    const_data["tickets"][str(after.channel.id)] = {
                        "category": category,
                        "author_id": int(user_id),
                        "listen": True,
                        "past_messages": []
                    }
                    save_data()

typing_stack = {}

@client.event
async def on_raw_typing(payload: discord.RawTypingEvent):
    global typing_stack
    typing_stack[f'{payload.channel_id},{payload.user_id}'] = int(payload.timestamp.timestamp())

rate_limit: list[int] = []
reaction_limit: dict[int, int] = {}
message_stack = {}

@client.event
async def on_message(message: discord.Message):
    global message_stack, rate_limit, typing_stack, reaction_limit, const_data
    if message.author.id != client.user.id: # stop being aware of self-messages

        if message.content.startswith("@LuxuryHelper") or message.content.startswith(f"<@{client.user.id}>"): # commands
            content = message.clean_content.replace(f"<@{client.user.id}>", "").replace(f"@LuxuryHelper", "").lstrip()

            if content.replace(' ', '') == 'stop':
                if const_data['tickets'].get(str(message.channel.id)):
                    const_data['tickets'][str(message.channel.id)]['listen'] = False
                    save_data()
                    await message.add_reaction("👍")
                else:
                    await message.reply("Hmm, I don't think this is a ticket, so I can't stop auto-reply.")
            
            elif content.replace(' ', '') == 'start':
                if const_data['tickets'].get(str(message.channel.id)):
                    const_data['tickets'][str(message.channel.id)]['listen'] = True
                    save_data()
                    await message.add_reaction("👍")
                else:
                    await message.reply("Hmm, I don't think this is a ticket, so I can't start auto-reply.")
            
            elif content.startswith('block') and message.author.guild_permissions.administrator:
                if "<@" in message.content.replace(f"<@{client.user.id}>", ""):
                    block_id = message.content.replace(f"<@{client.user.id}>", "").split("<@")[1].split(">")[0]
                elif "<#" in message.content:
                    block_id = message.content.split("<#")[1].split(">")[0]
                else:
                    block_id = str(message.channel.id)
                
                if block_id in const_data["blocked"]:
                    await message.reply("Seems like its already blocked.")
                else:
                    const_data["blocked"].append(block_id)
                    save_data()
                    
                    await message.reply(f"Blocked ID: {block_id}")
            
            elif content.startswith('unblock') and message.author.guild_permissions.administrator:
                if "<@" in message.content.replace(f"<@{client.user.id}>", ""):
                    block_id = message.content.replace(f"<@{client.user.id}>", "").split("<@")[1].split(">")[0]
                elif "<#" in message.content:
                    block_id = message.content.split("<#")[1].split(">")[0]
                else:
                    block_id = str(message.channel.id)
                
                if block_id not in const_data["blocked"]:
                    await message.reply("Seems like its already unblocked.")
                else:
                    const_data["blocked"].remove(block_id)
                    save_data()
                    
                    await message.reply(f"Unblocked ID: {block_id}")

            else:
                if str(message.author.id) not in const_data['blocked'] and str(message.channel.id) not in const_data["blocked"]:
                    msg = None
                    if not content: # check if the user said anything in the message before doing what they replied to
                        if message.reference:
                            if message.reference.cached_message:
                                replied_message = message.reference.cached_message
                            else:
                                replied_message = None
                                if message.reference.channel_id != message.channel.id:
                                    channel = client.get_channel(message.reference.channel_id)
                                else:
                                    channel = message.channel
                                
                                if channel:
                                    replied_message = await channel.fetch_message(message.reference.message_id)
                            
                            if replied_message:
                                msg = replied_message
                                msg_content = replied_message.clean_content.replace(f"<@{client.user.id}>", "").replace(f"@LuxuryHelper", "").lstrip()
                        
                        if not msg: # no content, and no replied message
                            return
                    
                    if not msg:
                        msg = message
                        msg_content = content
                    
                    if rate_limit.count(message.author.id) <= 2:
                        rate_limit.append(message.author.id)
                        
                        async with message.channel.typing():
                            try:
                                ai_reply = await ai.reply(msg_content, list(channel_ids.values()))
                            except:
                                ai_reply = "Uh oh, seems like something went wrong, please try again!"
                        
                        mentions = discord.AllowedMentions.none()
                        mentions.replied_user = True
                        await msg.reply(ai_reply, allowed_mentions=mentions)
                        
                        try: rate_limit.remove(message.author.id)
                        except: pass
                    
                    else:
                        current_time = int(time.time())
                        if reaction_limit.get(message.author.id, 0) < current_time - 15:
                            reaction_limit[message.author.id] = current_time
                            await message.add_reaction('⏳')
        
        elif "ticket" in getattr(message.channel.category, "name", "").lower():
            if const_data["tickets"].get(str(message.channel.id)):
                if const_data["tickets"][str(message.channel.id)]['listen'] and const_data["tickets"][str(message.channel.id)]['author_id'] == message.author.id:
                    
                    if not message_stack.get(str(message.channel.id)):
                        message_stack[str(message.channel.id)] = [(message.clean_content, message)]
                        await message.add_reaction('👀')
                    else:
                        message_stack[str(message.channel.id)].append((message.clean_content, message))

                    while True:
                        await asyncio.sleep(5)
                        current_time = int(time.time())
                        if message_stack[str(message.channel.id)][-1][1].id == message.id: # check if anymore messages have been received
                            if typing_stack.get(f'{message.channel.id},{message.author.id}', 0) < current_time - 12: # check if user has finished typing
                                # no typing pings in last 12 seconds, start to answer
                                try: await message_stack[str(message.channel.id)][0][1].clear_reaction('👀')
                                except: pass
                                break
                            else:
                                # not finished typing, contine checking every 5 seconds
                                continue
                        else:
                            # if a new message has been received, discard this coroutine
                            return
                    
                    try: del typing_stack[f'{message.channel.id},{message.author.id}']
                    except: pass

                    content = '. '.join(msg[1].clean_content for msg in message_stack[str(message.channel.id)])
                    try: del message_stack[str(message.channel.id)]
                    except: pass

                    if rate_limit.count(message.author.id) <= 2:
                        rate_limit.append(message.author.id)
                        
                        async with message.channel.typing():
                            try:
                                ai_reply = await ai.reply(content, list(channel_ids.values()))
                            except:
                                ai_reply = "Uh oh, seems like something went wrong, please try again!"
                        
                        mentions = discord.AllowedMentions.none()
                        mentions.replied_user = True
                        await message.reply(ai_reply, allowed_mentions=mentions)
                        
                        try: rate_limit.remove(message.author.id)
                        except: pass

                        
                        const_data["tickets"][str(message.channel.id)]['past_messages'].append(content)
                        save_data()
                    
                    else:
                        current_time = int(time.time())
                        if reaction_limit.get(message.author.id, 0) < current_time - 15:
                            reaction_limit[message.author.id] = current_time
                            await message.add_reaction('⏳')

                elif const_data["tickets"][str(message.channel.id)]['listen'] and const_data["tickets"][str(message.channel.id)]['author_id'] != message.author.id and not message.author.bot:
                    const_data['tickets'][str(message.channel.id)]['listen'] = False
                    save_data()
                    await message.add_reaction("✋")


client.run(bot_token)