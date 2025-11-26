import os
import requests
from bs4 import BeautifulSoup
import asyncio
import telegram
import logging
from time import sleep
import time
import re
import threading
from flask import Flask, jsonify
import sys
import traceback

# Configure logging to show ALL messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class KenoCloudMonitor:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        logger.info(f"Initializing monitor with token: {self.telegram_token[:10]}... and chat_id: {self.chat_id}")
        
        if not self.telegram_token or not self.chat_id:
            logger.error("❌ MISSING TELEGRAM CREDENTIALS")
            raise ValueError("Missing Telegram credentials")
            
        try:
            self.bot = telegram.Bot(token=self.telegram_token)
            self.last_detected_numbers = set()
            self.last_alert_time = 0
            self.alert_cooldown = 10
            self.session = requests.Session()
            
            # Set headers to mimic real browser
            self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            self.session.headers.update(self.headers)
            self.session.timeout = 10
            
            logger.info("✅ Monitor initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize monitor: {e}")
            raise

    def fetch_website_content(self):
        """Fetch website content"""
        try:
            url = f'https://flashsport.bet/?t={int(time.time()*1000)}'
            logger.debug("🔄 Fetching website...")
            response = self.session.get(url, timeout=8)
            response.raise_for_status()
            logger.debug("✅ Website fetched successfully")
            return response.text
        except Exception as e:
            logger.warning(f"⚠️ Fetch error: {e}")
            return None

    def detect_bright_numbers(self, html_content):
        """Detect bright numbers"""
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bright_numbers = set()
            
            # Multiple detection strategies
            bright_indicators = ['blink', 'flash', 'pulse', 'glowing', 'highlight', 'active', 'preview']
            
            # Strategy 1: Class-based detection
            for indicator in bright_indicators:
                elements = soup.find_all(class_=re.compile(indicator, re.IGNORECASE))
                for element in elements:
                    text = element.get_text().strip()
                    if text.isdigit() and 1 <= int(text) <= 80:
                        bright_numbers.add(int(text))
                        logger.info(f"🎯 Found number {text} via class: {indicator}")
            
            # Strategy 2: Style-based detection
            styled_elements = soup.find_all(style=re.compile('blink|flash|glow|animation', re.IGNORECASE))
            for element in styled_elements:
                text = element.get_text().strip()
                if text.isdigit() and 1 <= int(text) <= 80:
                    bright_numbers.add(int(text))
                    logger.info(f"🎯 Found number {text} via style")
            
            # Strategy 3: Regex patterns
            patterns = [
                r'class="[^"]*(blink|flash|pulse)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'style="[^"]*(animation|blink)[^"]*"[^>]*>.*?(\d{1,2})<'
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    for group in match.groups():
                        if group and group.isdigit() and 1 <= int(group) <= 80:
                            bright_numbers.add(int(group))
            
            # Filter false positives
            if len(bright_numbers) > 15:
                logger.debug("🔍 Too many numbers, likely false positive")
                return set()
                
            if bright_numbers:
                logger.info(f"🔍 Detected numbers: {bright_numbers}")
            else:
                logger.debug("🔍 No bright numbers detected")
                
            return bright_numbers
            
        except Exception as e:
            logger.error(f"❌ Detection error: {e}")
            return set()

    async def send_telegram_alert(self, numbers, message_type="bright"):
        """Send alert via Telegram"""
        if not numbers and message_type == "bright":
            return
        
        current_time = time.time()
        
        if message_type == "bright" and (current_time - self.last_alert_time) < self.alert_cooldown:
            logger.debug("⏳ Alert cooldown active")
            return
        
        try:
            if message_type == "bright":
                message = f"🚨 **KENO BRIGHT NUMBERS!** 🚨\n🎯 **{sorted(numbers)}**\n⏰ {time.strftime('%H:%M:%S')}"
                self.last_alert_time = current_time
            else:
                message = f"📊 **Monitor Status**\n✅ System running\n⏰ {time.strftime('%H:%M:%S')}\n⚡ Active monitoring"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"📤 Telegram {'alert' if message_type == 'bright' else 'status'} sent")
                
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}")

    async def single_check(self):
        """Perform a single check"""
        try:
            html_content = self.fetch_website_content()
            if html_content:
                current_numbers = self.detect_bright_numbers(html_content)
                
                if (current_numbers and 
                    current_numbers != self.last_detected_numbers and
                    1 <= len(current_numbers) <= 15):
                    
                    logger.info(f"🎯 BRIGHT NUMBERS FOUND: {current_numbers}")
                    await self.send_telegram_alert(current_numbers, "bright")
                    self.last_detected_numbers = current_numbers
                    
        except Exception as e:
            logger.error(f"❌ Check error: {e}")

# Global monitoring state
monitor_state = {
    "active": True,
    "restart_count": 0,
    "last_restart": time.time(),
    "total_checks": 0,
    "last_check": time.time()
}

async def continuous_monitoring():
    """Continuous monitoring loop"""
    logger.info("🚀 STARTING CONTINUOUS MONITORING")
    
    check_interval = 3  # 3 seconds between checks
    
    while monitor_state["active"]:
        try:
            monitor = KenoCloudMonitor()
            
            # Send startup message
            try:
                await monitor.send_telegram_alert(set(), "status")
                logger.info("✅ Startup message sent")
            except Exception as e:
                logger.error(f"❌ Startup message failed: {e}")
            
            # Continuous monitoring loop
            check_count = 0
            error_count = 0
            
            while monitor_state["active"] and error_count < 10:
                try:
                    start_time = time.time()
                    
                    await monitor.single_check()
                    
                    monitor_state["total_checks"] += 1
                    monitor_state["last_check"] = time.time()
                    check_count += 1
                    error_count = 0  # Reset error count on success
                    
                    # Log progress every 20 checks
                    if check_count % 20 == 0:
                        logger.info(f"📊 Monitoring active - {check_count} checks completed")
                    
                    # Send status every 60 checks (~3 minutes)
                    if check_count % 60 == 0:
                        try:
                            await monitor.send_telegram_alert(set(), "status")
                        except Exception as e:
                            logger.error(f"❌ Status update failed: {e}")
                    
                    # Calculate sleep time
                    processing_time = time.time() - start_time
                    sleep_time = max(1.0, check_interval - processing_time)
                    
                    await asyncio.sleep(sleep_time)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Monitoring error {error_count}/10: {e}")
                    await asyncio.sleep(5)  # Longer sleep on error
            
            # If we had too many errors, restart the monitor
            if error_count >= 10:
                logger.warning("🔄 Too many errors, restarting monitor...")
                monitor_state["restart_count"] += 1
                await asyncio.sleep(10)
                
        except Exception as e:
            logger.error(f"❌ Monitor crashed: {e}")
            monitor_state["restart_count"] += 1
            await asyncio.sleep(15)

async def main_monitor():
    """Main monitor function with restart protection"""
    max_restarts = 100
    restarts = 0
    
    while restarts < max_restarts and monitor_state["active"]:
        try:
            logger.info(f"🔄 Starting monitor (attempt {restarts + 1}/{max_restarts})")
            await continuous_monitoring()
        except Exception as e:
            restarts += 1
            logger.critical(f"💀 Monitor crashed completely: {e}")
            await asyncio.sleep(10)

def start_monitor_thread():
    """Start the monitor in a separate thread"""
    def run_monitor():
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main_monitor())
        except Exception as e:
            logger.critical(f"💀 Monitor thread died: {e}")
            # Restart the thread
            time.sleep(10)
            start_monitor_thread()
    
    thread = threading.Thread(target=run_monitor, name="KenoMonitor", daemon=True)
    thread.start()
    logger.info("✅ Monitor thread started")

# Flask Web Server
app = Flask(__name__)

@app.route('/')
def home():
    uptime = time.time() - monitor_state["last_restart"]
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    
    return f"""
    <html>
        <head>
            <title>Keno Monitor - ACTIVE</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f8ff; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                .status {{ color: #28a745; font-weight: bold; font-size: 20px; text-align: center; }}
                .info {{ margin: 20px 0; padding: 20px; background: #e8f4fd; border-radius: 10px; border-left: 5px solid #007bff; }}
                .stats {{ background: #fff3cd; border-left: 5px solid #ffc107; }}
                .live {{ color: #dc3545; font-weight: bold; animation: pulse 1s infinite; }}
                @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} 100% {{ opacity: 1; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 style="text-align: center; color: #333;">🎰 Keno Bright Numbers Monitor</h1>
                <div class="status">
                    <span class="live">🟢 LIVE MONITORING ACTIVE</span>
                </div>
                
                <div class="info">
                    <h3>📡 Monitoring Status</h3>
                    <p><strong>Website:</strong> https://flashsport.bet/</p>
                    <p><strong>Check Interval:</strong> <span class="live">Every 3 seconds</span></p>
                    <p><strong>Last Check:</strong> <span id="lastCheck">{time.strftime('%H:%M:%S', time.localtime(monitor_state['last_check']))}</span></p>
                    <p><strong>Status:</strong> <span id="status">ACTIVE & RUNNING</span></p>
                </div>
                
                <div class="info stats">
                    <h3>📊 System Statistics</h3>
                    <p><strong>Uptime:</strong> {hours}h {minutes}m</p>
                    <p><strong>Total Checks:</strong> {monitor_state['total_checks']}</p>
                    <p><strong>Restarts:</strong> {monitor_state['restart_count']}</p>
                    <p><strong>Last Restart:</strong> {time.strftime('%H:%M:%S', time.localtime(monitor_state['last_restart']))}</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    <p><strong>🚀 This monitor is actively checking for bright numbers every 3 seconds</strong></p>
                    <p>You will receive instant Telegram alerts when bright numbers appear!</p>
                </div>
                
                <script>
                    function updateTime() {{
                        document.getElementById('lastCheck').textContent = new Date().toLocaleTimeString();
                    }}
                    setInterval(updateTime, 1000);
                </script>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "monitoring": True,
        "total_checks": monitor_state["total_checks"],
        "restart_count": monitor_state["restart_count"],
        "last_check": monitor_state["last_check"],
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/monitor-status')
def monitor_status():
    active_threads = [t.name for t in threading.enumerate()]
    return jsonify({
        "monitor_active": monitor_state["active"],
        "active_threads": active_threads,
        "total_checks": monitor_state["total_checks"],
        "last_check": monitor_state["last_check"],
        "thread_count": threading.active_count()
    })

# Initialize application
def initialize_app():
    """Initialize the application"""
    logger.info("=" * 50)
    logger.info("🚀 INITIALIZING KENO MONITOR")
    logger.info("=" * 50)
    
    # Check environment variables
    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    if not os.getenv('TELEGRAM_CHAT_ID'):
        logger.error("❌ TELEGRAM_CHAT_ID not set!")
    
    # Start monitor thread
    logger.info("✅ Starting monitor thread...")
    start_monitor_thread()
    
    logger.info("✅ Application initialized successfully")

# Start everything
if __name__ == "__main__":
    # Initialize the app
    initialize_app()
    
    # Start Flask server
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Starting web server on port {port}")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.critical(f"💀 Web server failed: {e}")
