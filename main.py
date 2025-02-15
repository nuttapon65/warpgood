import os
import sqlite3
import pytz
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, send_from_directory, url_for
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# สร้างโฟลเดอร์ถ้ายังไม่มี
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ลบฐานข้อมูลเก่าถ้ามี
if os.path.exists('messages.db'):
    os.remove('messages.db')

# สร้างฐานข้อมูล SQLite และตารางถ้ายังไม่มี
conn = sqlite3.connect('messages.db')
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        timestamp TEXT
    )
""")
conn.commit()
conn.close()

def save_message(username, msg):
    timestamp = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (username, message, timestamp) VALUES (?, ?, ?)", (username, msg, timestamp))
    conn.commit()
    conn.close()

def get_latest_message():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("SELECT username, message, timestamp FROM messages ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row if row else ("", "", "")

def get_latest_image():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("SELECT message FROM messages WHERE username = 'system' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/input')
def input_page():
    return render_template('input.html')

@app.route('/display')
def display():
    username, message, timestamp = get_latest_message()
    try:
        files = os.listdir(app.config['UPLOAD_FOLDER'])
    except FileNotFoundError:
        files = []
    return render_template('display.html', username=username, message=message, timestamp=timestamp, images=files)

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

def save_image(filename):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (username, message, timestamp) VALUES (?, ?, ?)", 
              ("system", filename, datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file uploaded"})
    
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    save_image(filename)
    
    # แจ้งเตือนผ่าน Socket.IO ว่ามีรูปใหม่
    socketio.emit('newImage', {'filename': filename})
    
    return jsonify({"status": "success", "filename": filename})

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

@socketio.on('newMessage')
def handle_new_message(data):
    username = data.get("username", "แขก")
    message = data.get("message", "")
    save_message(username, message)
    socketio.emit('latestMessage', {'username': username, 'message': message})

@socketio.on('sendHeart')
def handle_heart():
    socketio.emit('sendHeart')

from waitress import serve  # ใช้ Waitress สำหรับ server บน Windows หรือ Linux
serve(app, host='0.0.0.0', port=3000)

