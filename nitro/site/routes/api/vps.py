from main import app, limiter, sniper

from flask import jsonify


@app.route('/api/v1/vps-stats', methods=['GET'])
@limiter.limit("8 per minute")
def vps_stats():
    formatted_data = []
    for instance_id, data in sniper.instances.copy().items():
        try:
            formatted_data.append({
                'instance_id': instance_id,
                'alts': "{:,}".format(int(data['alts'])),
                'servers': "{:,}".format(int(data['servers'])),
                'last_seen': data['last_seen']
            })
        except ValueError:
            formatted_data.append({
                'instance_id': instance_id,
                'alts': data['alts'],
                'servers': data['servers'],
                'last_seen': data['last_seen']
            })

    return jsonify(formatted_data)
