import gevent
from gevent import monkey
monkey.patch_all()

import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room

# Initialize Flask app and SocketIO
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))

# Initialize SocketIO with gevent
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Store the full runtime (sequence of status updates) for each laser
laser_runtimes = {}

@app.route('/')
def index():
    return render_template('LaserdashboardhomeV5flask.html')

@app.route('/laser/<laser_id>')
def laser_page(laser_id):
    return render_template(f'{laser_id}.html', laser_id=laser_id)

@socketio.on('connect')
def handle_connect():

    @socketio.on('join')
    def handle_join(data):
        laser_id = data.get('laser_id')
        if laser_id:
            room = laser_id
            join_room(room)

            # Send initial data
            if laser_id in laser_runtimes:
                emit('runtime_message', {
                    'laser': laser_id,
                    'runtime': laser_runtimes[laser_id]['runtime'],
                    'avg_cutting_time': laser_runtimes[laser_id].get('avg_cutting_time', 'N/A'),
                    'avg_idle_time': laser_runtimes[laser_id].get('avg_idle_time', 'N/A')
                }, room=room)
        else:
            room = 'dashboard'
            join_room(room)

            # Send data for all lasers
            for laser_id, runtime in laser_runtimes.items():
                emit('runtime_message', {
                    'laser': laser_id,
                    'runtime': runtime['runtime']
                }, room=room)

@socketio.on('runtime_update')
def handle_runtime_update(data):
    laser_id = data['laser']
    runtime = data.get('runtime', [])
    avg_cutting_time = data.get('avg_cutting_time')
    avg_idle_time = data.get('avg_idle_time')

    if not isinstance(runtime, list):
        return

    laser_runtimes[laser_id] = {
        'runtime': runtime,
        'avg_cutting_time': avg_cutting_time,
        'avg_idle_time': avg_idle_time
    }

    # Emit the updated data to the laser room
    emit('runtime_message', {
        'laser': laser_id,
        'runtime': runtime,
        'avg_cutting_time': avg_cutting_time,
        'avg_idle_time': avg_idle_time
    }, room=laser_id)

    # Also emit the update to the dashboard room
    emit('runtime_message', {
        'laser': laser_id,
        'runtime': runtime,
    }, room='dashboard')

if __name__ == '__main__':
    # Use SocketIO to run the app (with gevent for concurrency)
    socketio.run(app, host='0.0.0.0', port=1916)
