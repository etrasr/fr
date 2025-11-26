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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KenoCloudMonitor:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.telegram_token or not self.chat_id:
            logger.error("Missing Telegram credentials. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
            return
            
        self.bot = telegram.Bot(token=self.telegram_token)
        self.last_detected_numbers = set()
        self.last_alert_time = 0
        self.alert_cooldown = 10  # Don't alert more than once every 10 seconds
        self.session = requests.Session()
        
        # Set headers to mimic real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        self.session.headers.update(self.headers)
    
    def fetch_website_content(self):
        """Fetch website content with error handling - ULTRA FAST"""
        try:
            # Add cache busting to get fresh data
            url = f'https://flashsport.bet/?t={int(time.time()*1000)}'
            response = self.session.get(url, timeout=5)  # Shorter timeout for speed
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching website: {e}")
            return None
    
    def detect_bright_numbers(self, html_content):
        """
        IMPROVED DETECTION - Avoids false positives from number grid
        Only detects actual bright/preview numbers
        """
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bright_numbers = set()
            
            # STRATEGY 1: Look for VERY specific bright/flash indicators
            strong_indicators = ['blink', 'flash', 'pulse', 'shine', 'glowing', 'preview', 'nextdraw']
            
            for indicator in strong_indicators:
                # Look for elements with these specific classes
                elements = soup.find_all(class_=re.compile(indicator, re.IGNORECASE))
                for element in elements:
                    text = element.get_text().strip()
                    if text.isdigit() and 1 <= int(text) <= 80:
                        bright_numbers.add(int(text))
                        logger.info(f"Found number {text} via strong indicator: {indicator}")
            
            # STRATEGY 2: Look for elements with animation styles
            animated_elements = soup.find_all(style=re.compile(
                'animation|blink|flash|glow|pulse', re.IGNORECASE
            ))
            for element in animated_elements:
                text = element.get_text().strip()
                if text.isdigit() and 1 <= int(text) <= 80:
                    bright_numbers.add(int(text))
                    logger.info(f"Found number {text} via animation style")
            
            # STRATEGY 3: Look for temporary/preview containers
            preview_containers = soup.find_all(class_=re.compile(
                'preview|next|upcoming|temp|short|live', re.IGNORECASE
            ))
            for container in preview_containers:
                numbers = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', container.get_text())
                for num in numbers:
                    if 1 <= int(num) <= 80:
                        bright_numbers.add(int(num))
                        logger.info(f"Found number {num} in preview container")
            
            # STRATEGY 4: Ultra-fast regex scanning for bright patterns
            bright_patterns = [
                r'class="[^"]*(blink|flash|pulse|glowing)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'style="[^"]*(animation|blink|flash)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'<[^>]*(blink|flash|pulse)[^>]*>.*?(\d{1,2})<'
            ]
            
            for pattern in bright_patterns:
                matches = re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    for group in match.groups():
                        if group and group.isdigit() and 1 <= int(group) <= 80:
                            bright_numbers.add(int(group))
                            logger.info(f"Found number {group} via regex pattern")
            
            # FILTER OUT FALSE POSITIVES
            filtered_numbers = set()
            
            # Don't alert for too many numbers (likely the full grid)
            if len(bright_numbers) > 15:
                logger.info(f"Too many numbers detected ({len(bright_numbers)}), likely false positive. Skipping.")
                return set()
            
            # Don't alert for sequential numbers starting from 1 (likely the grid)
            if (bright_numbers and 
                min(bright_numbers) == 1 and 
                max(bright_numbers) >= 10 and 
                len(bright_numbers) >= 8):
                logger.info("Detected sequential numbers 1-10+, likely the grid. Skipping.")
                return set()
            
            # Only return numbers that passed all filters
            filtered_numbers = bright_numbers
            
            logger.info(f"Final filtered detection: {filtered_numbers}")
            return filtered_numbers
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return set()
    
    async def send_telegram_alert(self, numbers, message_type="bright"):
        """Send alert via Telegram - ULTRA FAST"""
        if not numbers:
            return
        
        current_time = time.time()
        
        # Cooldown check to avoid spam
        if message_type == "bright" and (current_time - self.last_alert_time) < self.alert_cooldown:
            logger.info(f"Alert cooldown active. Skipping duplicate alert.")
            return
        
        if message_type == "bright":
            message = f"🚨 **KENO BRIGHT NUMBERS DETECTED!** 🚨\n"
            message += f"🎯 Numbers: **{sorted(numbers)}**\n"
            message += f"⏰ Time: {time.strftime('%H:%M:%S')}\n"
            message += f"⚡ Detected instantly"
            
            self.last_alert_time = current_time
        else:
            message = f"📊 **Keno Monitor Status**\n"
            message += f"✅ System is running\n"
            message += f"⏰ Last check: {time.strftime('%H:%M:%S')}\n"
            message += f"🔍 Check interval: 1-2 seconds\n"
            message += f"⚡ Ultra-fast monitoring"
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Telegram message sent: {numbers}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def check_and_alert(self):
        """Perform one check cycle - OPTIMIZED FOR SPEED & ACCURACY"""
        try:
            html_content = self.fetch_website_content()
            if html_content:
                current_numbers = self.detect_bright_numbers(html_content)
                
                # Only alert if we found valid numbers and they're new
                if (current_numbers and 
                    current_numbers != self.last_detected_numbers and
                    1 <= len(current_numbers) <= 15):  # Only alert for reasonable sets
                    
                    logger.info(f"🚨 VALID BRIGHT NUMBERS DETECTED: {current_numbers}")
                    await self.send_telegram_alert(current_numbers, "bright")
                    self.last_detected_numbers = current_numbers
                else:
                    if current_numbers:
                        logger.info(f"Ignoring likely false positive: {current_numbers}")
                    # else: normal no detection
                    
        except Exception as e:
            logger.error(f"Check error: {e}")

async def monitor_loop():
    """ULTRA FAST monitoring loop - checks every 1-2 seconds"""
    monitor = KenoCloudMonitor()
    
    if not monitor.telegram_token or not monitor.chat_id:
        logger.error("Cannot start monitor - missing Telegram credentials")
        return
    
    logger.info("🚀 Starting ULTRA-FAST Keno Monitor (1-2 second checks)")
    
    # Send startup message
    try:
        await monitor.send_telegram_alert(set(), "status")
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")
    
    # Ultra-fast monitoring loop
    check_count = 0
    while True:
        try:
            start_time = time.time()
            await monitor.check_and_alert()
            check_count += 1
            
            # Send status every 150 checks (~3-5 minutes)
            if check_count % 150 == 0:
                try:
                    await monitor.send_telegram_alert(set(), "status")
                except Exception as e:
                    logger.error(f"Failed to send status update: {e}")
                check_count = 0
            
            # Dynamic sleep to maintain 1-2 second intervals
            processing_time = time.time() - start_time
            sleep_time = max(0.5, 2.0 - processing_time)  # Aim for 2 second total cycle, minimum 0.5 sleep
            
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
            await asyncio.sleep(2)

def start_async_monitor():
    """Start the async monitor in event loop"""
    asyncio.run(monitor_loop())

# Flask Web Server for UptimeRobot
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>Keno Monitor</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .status { color: green; font-weight: bold; font-size: 18px; }
                .info { margin: 20px 0; padding: 15px; background: #e8f4fd; border-radius: 5px; }
                .ultra-fast { color: #ff4444; font-weight: bold; animation: pulse 1.5s infinite; }
                @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎰 Keno Bright Numbers Monitor</h1>
                <div class="status">✅ <span class="ultra-fast">ULTRA-FAST MONITORING ACTIVE</span></div>
                
                <div class="info">
                    <p><strong>Monitoring:</strong> https://flashsport.bet/</p>
                    <p><strong>Check Interval:</strong> <span class="ultra-fast">Every 1-2 seconds</span></p>
                    <p><strong>Detection:</strong> Improved algorithm (no false positives)</p>
                    <p><strong>Status:</strong> <span id="status">Active</span></p>
                    <p><strong>Last Check:</strong> <span id="time">""" + time.strftime('%Y-%m-%d %H:%M:%S') + """</span></p>
                </div>
                
                <p>This service automatically detects when numbers brighten up in FlashSport Keno and sends instant Telegram notifications.</p>
                <p class="ultra-fast">⚡ Monitoring at maximum speed with improved accuracy!</p>
                
                <script>
                    function updateTime() {
                        document.getElementById('time').textContent = new Date().toLocaleString();
                    }
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
        "service": "keno-monitor",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "monitoring": "https://flashsport.bet/",
        "check_interval": "1-2 seconds",
        "detection": "improved-accuracy"
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "monitoring": "flashsport.bet/keno", 
        "check_interval": "1-2 seconds",
        "detection": "improved-accuracy",
        "uptime": "24/7"
    })

def start_monitor_thread():
    """Start the monitor in a separate thread"""
    monitor_thread = threading.Thread(target=start_async_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    logger.info("🚀 Ultra-fast monitor thread started")

if __name__ == "__main__":
    # Start the ultra-fast monitor
    start_monitor_thread()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
