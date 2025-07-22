from flask import Flask, request, render_template, jsonify
import json
import socket
import threading
import netifaces
import ipaddress
import os
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)
devices = []

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.get('user_input')
    print(f"User typed: {data}")
    return '', 204  # empty response with HTTP 204 No Content

#@app.route("/discover", methods=["POST"])
def broadcast_discovery():
    message = b'DISCOVER_REQUEST'
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(message, (get_subnet_broadcast(), 50000))
    sock.close()
    return '', 204

@app.route("/devices")
def send_devicelist():
    return jsonify(devices)

@app.route("/select", methods=["POST"])
def changeSelected():
    global chats
    global selected
    data = request.get_json()
    selected = data.get("selected")
    if 'chats' not in globals():
        if os.path.exists(f"chats/{selected}.json"):
            with open(f"chats/{selected}.json", "r") as chatfile:
                chats = json.load(chatfile)
        else:
            chats = []
    socketio.emit('new_message', chats)
    return "success"

@app.route("/send", methods=["POST"])
def send_message():
    global chats
    data = request.get_json()
    message = data.get("message").encode()
    target = str(data.get("to"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (target, 50001))
    sock.close()
    if os.path.exists(f"chats/{target}.json"):
        with open(f"chats/{target}.json", "r") as chatfile:
            chats = json.load(chatfile)
    else:
        chats = []
    chats.append({"type":"out", "message": message.decode()})
    with open(f"chats/{target}.json", "w") as chatfile:
        json.dump(chats, chatfile, indent=2)
    return "success"


def listen_for_message():
    global selected
    global chats
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', 50001))
    print("Listening for messages...")
    while True:
        data, addr = sock.recvfrom(1024)
        print(f"Received message {data}")
        if os.path.exists(f"chats/{addr[0]}.json"):
            with open(f"chats/{addr[0]}.json", "r") as chatfile:
                chats = json.load(chatfile)
        else:
            chats = []
        chats.append({"type":"in", "message": data.decode()})
        with open(f"chats/{addr[0]}.json", "w") as chatfile:
            json.dump(chats, chatfile, indent=2)
        socketio.emit('new_message', chats)

def listen_for_discovery():
    global devices
    own_ip = get_own_ip()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', 50000))
    print("Listening for discovery...")
    while True:
        data, addr = sock.recvfrom(1024)
        sender_ip = addr[0]
        if sender_ip == own_ip:
            continue
        else:
            if addr[0] not in devices:
                print(f"Received {data.decode()} from {addr[0]}")
                broadcast_discovery()
                devices.append(addr[0])
                socketio.emit('new_discovery')

def get_subnet_broadcast():
    gateway = netifaces.gateways()
    interface = gateway['default'][netifaces.AF_INET][1]
    address = netifaces.ifaddresses(interface)
    inet_info = address[netifaces.AF_INET][0]
    ip = inet_info['addr']
    netmask = inet_info['netmask']
    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
    broadcast = str(network.broadcast_address)
    return broadcast


def get_own_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == "__main__":
    listener_thread = threading.Thread(target=listen_for_discovery, daemon=True)
    listener_thread.start()
    message_thread = threading.Thread(target=listen_for_message, daemon=True)
    message_thread.start()
    broadcast_discovery()
    socketio.run(app, debug=False, use_reloader=False, port=5000)



