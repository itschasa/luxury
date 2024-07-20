from queue import Queue
import time
import traceback
from typing import Union
from dataclasses import dataclass

from oauth import http, token, tls, bot, exceptions 
from config import config
import utils
import db



join_queue = Queue()
"Queue of orders waiting to be completed (bot in guild)."

# needs to load orders from db
awaiting_guild_check: list[tuple[int, int]] = []
"List of `(order_id, guild_id)` that the bot is waiting to be invited to, or that are waiting to be rechecked."

oauth_link = f"https://discord.com/api/oauth2/authorize?client_id={config().discord_app.client_id}&permissions=268435457&response_type=code&redirect_uri={config().discord_app.redirect_uri}&scope=identify+guilds+bot"
"Link to oauth page for customers."


@dataclass
class order_product:
    item_key: int
    item_name: str
    quantity: int = 0
    filled: int = 0
    joins: int = 0
    failed: int = 0


@dataclass
class order:
    order_id: int
    data: dict[int, order_product]


current_order_handle: Union[None, order] = None


def handle_order(order_id: int):
    global current_order_handle

    utils.log.info(f'starting to handle order {order_id}')

    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''SELECT status, user_id, order_data, guild_id, role_ids FROM orders WHERE id = ?;''',
            [order_id]
        )
        raw_data: tuple[int, int, str, int, str] = cur.fetchone()
        status, user_id, order_data, guild_id, role_ids = raw_data
    except:
        utils.log.error(f'error getting order {order_id} from db')
        db.pool.release(conn, cur)
    else:
        if not bot.check_for_guild(guild_id):
            utils.log.info(f'bot is not in guild {guild_id}, adding to guild_check')
            awaiting_guild_check.append((order_id, guild_id))
            db.pool.release(conn, cur)
            return
        
        if status != 0:
            utils.log.info(f'order {order_id} is already handled')
            db.pool.release(conn, cur)
            try:
                bot.leave_guild(guild_id)
            except:
                utils.log.error(f'error leaving guild {guild_id} for order {order_id}: {traceback.format_exc()}')
            return

        try:
            cur.execute(
                '''UPDATE orders SET status = ? WHERE id = ?;''',
                [1, order_id]
            )
        except db.error:
            utils.log.error(f'error updating order {order_id} (continuing): {traceback.format_exc()}')

        db.pool.release(conn, cur)

        role_ids: list[int] = utils.jl(role_ids)
        order_data: list[tuple[int, int]] = utils.jl(order_data) # key, quantity

        current_order_handle = order(
            order_id,
            {
                key: order_product(
                    item_key  = key,
                    item_name = str(token.TokenTypes(key)),
                    quantity  = quantity
                ) for key, quantity in order_data
            }
        )

        bot_no_perms = False

        for key, _ in order_data:
            token_type = token.TokenTypes(key)
            
            
            tokens = token.search(token_type, guild_id)
            utils.log.debug(f'found {len(tokens)} tokens for {str(token_type)} not in guild {guild_id} for order {order_id}')
            while len(tokens) > 0 and current_order_handle.data[key].filled < current_order_handle.data[key].quantity:
                tkn = tokens.pop(0)
                
                # check for boost ids, if needed
                if token_type.boost:
                    if not tkn.boost_ids:
                        try:
                            tkn.update_boost_ids()
                        except:
                            utils.log.error(f'error updating boost ids for token {tkn.user_id} for order {order_id}: {traceback.format_exc()}')
                            current_order_handle.data[key].failed += 1
                        
                        else:
                            if not tkn.boost_ids:
                                utils.log.info(f'token {tkn.user_id} has no boost ids for order {order_id}')
                                current_order_handle.data[key].failed += 1
                
                # join guild, if not boost, or if boost and boost ids
                if not token_type.boost or tkn.boost_ids:
                    try:
                        joined = tkn.join_server(guild_id, role_ids)
                    except exceptions.FailedToJoin:
                        utils.log.error(f'token {tkn.user_id} failed to join guild {guild_id} for order {order_id}: FailedToJoin exception')
                        current_order_handle.data[key].failed += 1
                    except exceptions.BotNoPerms:
                        utils.log.error(f'token {tkn.user_id} failed to join guild {guild_id} for order {order_id}: BotNoPerms exception')
                        current_order_handle.data[key].failed += 1
                        bot_no_perms = True
                        break
                    except:
                        utils.log.error(f'token {tkn.user_id} failed to join guild {guild_id} for order {order_id}: {traceback.format_exc()}')
                        current_order_handle.data[key].failed += 1
                    
                    else:
                        # if already in server, and not a boost token, mark as failed
                        if not joined and not token_type.boost:
                            utils.log.warn(f'token {tkn.user_id} was already in {guild_id} for order {order_id}, skipping')
                            current_order_handle.data[key].failed += 1
                        else:
                            # if joined correctly
                            if joined:
                                current_order_handle.data[key].joins += 1
                                utils.log.info(f'token {tkn.user_id} joined guild {guild_id} for order {order_id}')
                            
                            # if already in server, but is a boost token
                            else:
                                utils.log.info(f'token {tkn.user_id} was already in {guild_id} for order {order_id}, skipping')

                            # boost server, if boost token
                            if token_type.boost:
                                for boost_id in tkn.boost_ids:
                                    if current_order_handle.data[key].filled < current_order_handle.data[key].quantity:
                                        try:
                                            tkn.boost_server(guild_id, boost_id)
                                        except:
                                            utils.log.error(f'token {tkn.user_id} failed to boost guild {guild_id} for order {order_id}: {traceback.format_exc()}')
                                            current_order_handle.data[key].failed += 1
                                        
                                        else:
                                            utils.log.info(f'token {tkn.user_id} boosted guild {guild_id} for order {order_id}')
                                            current_order_handle.data[key].filled += 1

                            # if not a boost token, mark as filled
                            else:
                                current_order_handle.data[key].filled += 1
                
                
                try:
                    tkn.save_to_db()
                except:
                    utils.log.error(f'error saving token {tkn.user_id} to db for order {order_id}: {traceback.format_exc()}')

            utils.log.info(f'finished handling {str(token_type)} part of order {order_id}: {current_order_handle.data[key].filled}/{current_order_handle.data[key].quantity} filled, {current_order_handle.data[key].joins} joined, {current_order_handle.data[key].failed} failed')

            if current_order_handle.data[key].filled < current_order_handle.data[key].quantity:
                utils.log.warn(f'not enough stock ({str(token_type)}) to fill order {order_id} ({current_order_handle.data[key].filled}/{current_order_handle.data[key].quantity})')

            if bot_no_perms:
                utils.log.error(f'bot has no perms in guild {guild_id} for order {order_id}, cancelling order')
                break

        refund_amount = 0
        for key, prod in current_order_handle.data.items():
            if prod.filled < prod.quantity:
                refund_amount += (prod.quantity - prod.filled) * token.TokenTypes(prod.item_key).cost
        
        conn, cur = db.pool.get()
        if refund_amount > 0:
            payment_id = utils.snowflake.new()

            try:
                cur.execute(
                    '''SELECT balance FROM payments WHERE user_id = ?
                    ORDER BY rowid DESC LIMIT 1;''',
                    [user_id]
                )
                balance = cur.fetchone()
                if balance is None:
                    balance = 0
                else:
                    balance = balance[0]
            except db.error:
                utils.log.error(f'error getting balance for user {user_id} for order {order_id}: {traceback.format_exc()}')
            
            try:
                cur.execute(
                    '''INSERT INTO payments (id, change, user_id, reason, order_id, balance) VALUES (?, ?, ?, ?, ?, ?);''',
                    [payment_id, refund_amount, user_id, f'Refund on Order #{order_id}{" (BotNoPerms)" if bot_no_perms else ""}', order_id, balance+refund_amount]
                )
            except db.error:
                utils.log.error(f'error refunding (+{refund_amount}) user {user_id} for order {order_id}: {traceback.format_exc()}')

        try:
            cur.execute(
                '''UPDATE orders SET status = ?, order_data = ? WHERE id = ?;''',
                [
                    2,
                    utils.jd([
                        {
                            'item_key': key,
                            'item_name': data.item_name,
                            'quantity': data.quantity,
                            'filled': data.filled,
                            'joins': data.joins,
                            'failed': data.failed
                        } for key, data in current_order_handle.data.items()
                    ]),
                    order_id
                ]
            )
        except db.error:
            utils.log.error(f'error updating order {order_id}: {traceback.format_exc()}')
        finally:
            db.pool.release(conn, cur)
        
        try:
            bot.leave_guild(guild_id)
        except:
            utils.log.error(f'error leaving guild {guild_id} for order {order_id}: {traceback.format_exc()}')

        utils.log.info(f'finished handling order {order_id}')
        current_order_handle = None


def thread_order_handler():
    while True:
        order_id = join_queue.get()
        try:
            handle_order(order_id)
        except:
            utils.log.error(f'error handling order {order_id}: {traceback.format_exc()}')

        time.sleep(5)


def thread_guild_checker():
    while True:
        time.sleep(20)
        try:
            order_id, guild_id = awaiting_guild_check.pop(0)
        except IndexError:
            continue
        else:
            if bot.check_for_guild(guild_id):
                join_queue.put(order_id)
                utils.log.info(f'check for guild on {guild_id} succeeded, added {order_id} to queue')
            else:
                utils.log.info(f'check for guild on {guild_id} failed, re-adding {order_id} to guild_check')
                awaiting_guild_check.append((order_id, guild_id))


def startup_add_to_queue():
    conn, cur = db.pool.get()
    try:
        cur.execute(
            '''SELECT id FROM orders WHERE status = 1;'''
        )
        orders: list[tuple[int]] = cur.fetchall()
    except db.error:
        db.pool.release(conn, cur)
        utils.log.error(f'error getting orders (status=1) from db for startup add to queue: {traceback.format_exc()}')
    else:
        if orders:
            utils.log.warn(f'found {len(orders)} orders with status=1, needs to be resolved manually')
        else:
            utils.log.info('no orders with status=1 found')

    #try:
    #    cur.execute(
    #        '''SELECT id, guild_id FROM orders WHERE status = 0;'''
    #    )
    #    orders: list[tuple[int, int]] = cur.fetchall()
    #except db.error:
    #    db.pool.release(conn, cur)
    #    utils.log.error(f'error getting orders (status=0) from db for startup add to queue: {traceback.format_exc()}')
    #else:
    #    utils.log.info(f'adding {len(orders)} orders to guild_check')
    #    db.pool.release(conn, cur)
    #    for order_id, guild_id in orders:
    #        awaiting_guild_check.append((order_id, guild_id))
