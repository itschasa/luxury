from queue import Queue

from config import config
import utils



snowflake_counter = {}
snowflake_queue = Queue()
for x in range(16):
    snowflake_queue.put(x)
    snowflake_counter[x] = 0


def new(current_time: int = None) -> int:
    if current_time is None:
        current_time = utils.ms()
        
    process_id = snowflake_queue.get()
    
    time_minus_epoch = current_time - config().snowflake_epoch

    binary_time = bin(time_minus_epoch)

    # [2:] to remove "0b"
    # [-n:] to get the last n digits
    binary_process_id = bin(process_id)[2:].zfill(6)[-6:]
    binary_counter = bin(snowflake_counter[process_id])[2:].zfill(10)[-10:]

    snowflake = int(binary_time + binary_process_id + binary_counter, 2)
    
    snowflake_counter[process_id] += 1

    snowflake_queue.put(process_id)
    return snowflake


def time(snowflake: int) -> int:
    # Shift the bits of the snowflake to the right to remove the process ID and counter
    timestamp = snowflake >> (6 + 10)  # 6 bits for process ID, 10 bits for counter

    # Add the epoch back to get the original timestamp
    original_timestamp = timestamp + config().snowflake_epoch

    return original_timestamp