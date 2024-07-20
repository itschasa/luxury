from main import app, limiter
import utils
import database
import config
from itertools import chain

from flask import request
import re, time, json

time_re = re.compile(r'(\d+)(\D+)')

# title, colour
line_metadata = {
    'total': ('Total Claims', '129, 82, 247'),
    'boost': ('Boost Claims', '206, 135, 250'),
    'basic': ('Basic Claims', '48, 111, 222'),
    'classic': ('Classic Claims', '62, 58, 181'),
    'avg_time': ('Avg. Snipe Delay (ms)', '245, 104, 88')
}
# month -> week = multiply by 4, etc
time_order = {'h': 60, '3h': 3, '6h': 2, '12h': 2, 'd': 2, 'w': 7, 'm': 4}
# hours -> mins = hours * 3600, etc
time_order_translate = {'h': 3600, '3h': 10800, '6h': 21600, '12h': 43200, 'd': 86400, 'w': 604800, 'm': 2419200}
# hour -> mins, etc
mins_conversions = {
    'h': 60,
    'd': 1440,
    'm': 40320
}
# min+max points on graph
min_points = 8
max_points = 50

@app.route('/api/v1/graph', methods=['GET'])
@limiter.limit("1 per 2 seconds", deduct_when=lambda response: response.status_code == 200)
def api_graph():
    user_id = utils.authenticate(request)
    if user_id == False:
        return utils.j({'error': True, 'message': "Unauthenticated."}), 401


    time_raw = request.args.get('time', '7d')
    match = time_re.match(time_raw)
    if match:
        time_number = int(match.group(1))
        time_character = match.group(2)
        if time_character not in ('h', 'd', 'm'):
            return utils.j({'error': True, 'message': "Data Error."}), 400
    else:
        return utils.j({'error': True, 'message': "Data Error."}), 400

    time_in_mins = time_number * mins_conversions[time_character]

    time_iter = time_in_mins # amount of points
    time_chunk = None        # time used on each point
    for key, val in time_order.items():
        time_iter = int(time_iter / val)
        if time_iter >= min_points and time_iter <= max_points:
            time_chunk = time_order_translate[key]
            break
    
    if time_chunk is None:
        return utils.j({'error': True, 'message': "Failed to process time appropriately."}), 500
    
    current_time = request.args.get('current', int(time.time()), type=int)

    db = database.Connection(config.db_name)
    db_data = db.query('orders', ['claim_data'], {}, False)
    loaded_data = [json.loads(json_str[1]) for json_str in db_data]
    flattened_data = list(chain.from_iterable(loaded_data))
    sorted_data = sorted(flattened_data, key=lambda d: d['time'], reverse=True)
    # [{
    #     "instance": instance_id,
    #     "time": int(time.time()),
    #     "type": sniper_translation[request_data["snipe"]],
    #     "snipe_time": request_data["time"]
    # }]
    list_pointer = 0

    dataset = {
        'total': [],
        'boost': [],
        'classic': [],
        'basic': [],
        'avg_time': [],
    }
    labels = []

    for x in range(time_iter):
        smallest_time = current_time - (time_chunk * (x+1))
        chunk_data = {
            'total': 0,
            'boost': 0,
            'classic': 0,
            'basic': 0,
            'avg_time': []
        }
        labels.append(f"{current_time - (time_chunk * x)}-{smallest_time}")
        while True:
            if list_pointer < len(sorted_data):
                if sorted_data[list_pointer]['time'] >= smallest_time:
                    chunk_data['total'] += 1
                    chunk_data[sorted_data[list_pointer]['type'].split(' ')[0].lower()] += 1
                    snipe_time = sorted_data[list_pointer].get('snipe_time', '0ms')
                    chunk_data['avg_time'].append(
                        int(float(snipe_time[:-2]))
                        if 'ms' in snipe_time
                        else int(float(snipe_time[:-1]) * 1000)
                    )
                    list_pointer += 1
                else:
                    break
            else:
                break
        

        if not chunk_data['avg_time']: chunk_data['avg_time'] = [0]
        if sum(chunk_data['avg_time']) != 0: chunk_data['avg_time'] = list(filter(lambda val: val != 0, chunk_data['avg_time']))

        chunk_data['avg_time'] = int(sum(chunk_data['avg_time']) / len(chunk_data['avg_time']))
        for key, val in chunk_data.items():
            dataset[key].append(val)
        
    for key in dataset.keys():
        dataset[key].reverse()
    labels.reverse()
    
    dataset_formatted = []
    for key, val in dataset.items(): 
        dataset_formatted.append({
            'label': line_metadata[key][0],
            'data': val,
            'fill': False,
            'borderColor': f'rgba({line_metadata[key][1]}, 1)',
            'backgroundColor': f'rgba({line_metadata[key][1]}, 0.5)',
            'borderWidth': 2,
            'yAxisID': 'r' if key == 'avg_time' else 'l',
        })
    
    return utils.j({'labels': labels, 'datasets': dataset_formatted}), 200