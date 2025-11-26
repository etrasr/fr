from flask import Flask, jsonify
import threading
import time
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>Keno Monitor</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .status { color: green; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>🎰 Keno Bright Numbers Monitor</h1>
            <p class="status">✅ System is running and monitoring FlashSport Keno</p>
            <p>This service checks for bright/preview numbers every 5 seconds.</p>
            <p>You will receive Telegram alerts when bright numbers appear.</p>
            <p>Last checked: <span id="time">""" + time.strftime('%Y-%m-%d %H:%M:%S') + """</span></p>
            <script>
                function updateTime() {
                    document.getElementById('time').textContent = new Date().toLocaleString();
                }
                setInterval(updateTime, 1000);
            </script>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "keno-monitor",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "monitoring": "flashsport.bet/keno",
        "check_interval": "5 seconds",
        "uptime": "24/7"
    })

if __name__ == "__main__":
    # Import and start the monitor
    from app import start_monitor_thread
    start_monitor_thread()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
