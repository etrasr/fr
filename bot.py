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
import concurrent.futures

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
        ULTRA FAST detection optimized for speed
        """
        if not html_content:
            return set()
        
        try:
            bright_numbers = set()
            
            # STRATEGY 1: Ultra-fast regex scanning (bypass BeautifulSoup when possible)
            # Look for number patterns with bright indicators nearby
            bright_patterns = [
                r'class="[^"]*(bright|highlight|active|blink|flash|glow|selected|current|new|preview)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'>(\d{1,2})<[^<]*(bright|highlight|active|blink|flash|glow|selected|current|new|preview)',
                r'style="[^"]*(bright|highlight|glow|animation|blink)[^"]*"[^>]*>.*?(\d{1,2})<'
            ]
            
            for pattern in bright_patterns:
                matches = re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    # Extract the number from different capture groups
                    for group in match.groups():
                        if group and group.isdigit() and 1 <= int(group) <= 80:
                            bright_numbers.add(int(group))
            
            # STRATEGY 2: Fast BeautifulSoup scan only if needed
            if not bright_numbers:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Look for elements with bright-related attributes
                bright_indicators = ['bright', 'highlight', 'active', 'blink', 'flash', 'glow', 'selected', 'current', 'new', 'preview']
                
                for indicator in bright_indicators:
                    elements = soup.find_all(class_=re.compile(indicator, re.IGNORECASE))
                    for element in elements:
                        text = element.get_text().strip()
                        if text.isdigit() and 1 <= int(text) <= 80:
                            bright_numbers.add(int(text))
                
                # Check inline styles
                elements_with_style = soup.find_all(style=re.compile('bright|glow|blink|animation', re.IGNORECASE))
                for element in elements_with_style:
                    text = element.get_text().strip()
                    if text.isdigit() and 1 <= int(text) <= 80:
                        bright_numbers.add(int(text))
            
            # STRATEGY 3: Small number set detection
            if not bright_numbers:
                # Quick regex to find all numbers on page
                all_numbers = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', html_content)
                unique_numbers = set(all_numbers)
                
                # If we have a small subset (likely preview), use them
                if 1 <= len(unique_numbers) <= 10:
                    for num in unique_numbers:
                        bright_numbers.add(int(num))
            
            return bright_numbers
            
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
        """Perform one check cycle - OPTIMIZED FOR SPEED"""
        try:
            html_content = self.fetch_website_content()
            if html_content:
                current_numbers = self.detect_bright_numbers(html_content)
                
                # Only alert if we found some numbers (not empty) and they're new
                if current_numbers and current_numbers != self.last_detected_numbers:
                    logger.info(f"🚨 NEW BRIGHT NUMBERS: {current_numbers}")
                    await self.send_telegram_alert(current_numbers, "bright")
                    self.last_detected_numbers = current_numbers
                # else:
                #     logger.info("No new bright numbers detected")
            # else:
            #     logger.warning("Failed to fetch website content")
                
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
    await monitor.send_telegram_alert(set(), "status")
    
    # Ultra-fast monitoring loop
    check_count = 0
    while True:
        try:
            start_time = time.time()
            await monitor.check_and_alert()
            check_count += 1
            
            # Send status every 100 checks (~2-3 minutes)
            if check_count % 100 == 0:
                await monitor.send_telegram_alert(set(), "status")
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
                    <p><strong>Status:</strong> <span id="status">Active</span></p>
                    <p><strong>Last Check:</strong> <span id="time">""" + time.strftime('%Y-%m-%d %H:%M:%S') + """</span></p>
                    <p><strong>Optimized for:</strong> Instant detection of brief bright number events</p>
                </div>
                
                <p>This service automatically detects when numbers brighten up in FlashSport Keno and sends instant Telegram notifications.</p>
                <p class="ultra-fast">⚡ Monitoring at maximum speed to never miss brief bright number events!</p>
                
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
        "optimization": "ultra-fast"
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "monitoring": "flashsport.bet/keno", 
        "check_interval": "1-2 seconds",
        "optimization": "ultra-fast",
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
