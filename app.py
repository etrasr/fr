import os
import requests
from bs4 import BeautifulSoup
import asyncio
import telegram
import logging
from time import sleep
import schedule
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
        self.session = requests.Session()
        
        # Set headers to mimic real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self.headers)
    
    def fetch_website_content(self):
        """Fetch website content with error handling"""
        try:
            response = self.session.get('https://flashsport.bet/', timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching website: {e}")
            return None
    
    def detect_bright_numbers(self, html_content):
        """
        Advanced detection without relying on lxml or specific CSS classes
        """
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bright_numbers = set()
            
            logger.info("Scanning for bright numbers...")
            
            # Strategy 1: Find all number elements (spans, divs, etc.)
            number_elements = soup.find_all(['span', 'div', 'li', 'td', 'button'])
            
            for element in number_elements:
                text = element.get_text().strip()
                # Check if text is a number between 1-80
                if text.isdigit() and 1 <= int(text) <= 80:
                    # Check for bright indicators in class or style
                    element_class = ' '.join(element.get('class', []))
                    element_style = element.get('style', '')
                    element_id = element.get('id', '')
                    
                    all_attributes = element_class + ' ' + element_style + ' ' + element_id
                    
                    bright_indicators = [
                        'bright', 'highlight', 'active', 'blink', 'flash', 
                        'glow', 'selected', 'current', 'new', 'preview',
                        'animation', 'pulse', 'shine'
                    ]
                    
                    if any(indicator in all_attributes.lower() for indicator in bright_indicators):
                        bright_numbers.add(int(text))
                        logger.info(f"Found bright number {text} via attributes: {all_attributes}")
            
            # Strategy 2: Look for numbers in likely containers
            if not bright_numbers:
                logger.info("Trying container-based detection...")
                containers = soup.find_all(['div', 'section'], class_=True)
                for container in containers:
                    container_class = ' '.join(container.get('class', []))
                    container_indicators = ['keno', 'game', 'number', 'result', 'draw', 'live', 'preview']
                    
                    if any(word in container_class.lower() for word in container_indicators):
                        # Check if this container has bright styling
                        container_style = container.get('style', '')
                        if any(word in container_style.lower() for word in ['bright', 'glow', 'animation']):
                            container_text = container.get_text()
                            numbers = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', container_text)
                            if 1 <= len(numbers) <= 15:  # Likely not the full grid
                                for num in numbers:
                                    bright_numbers.add(int(num))
                                logger.info(f"Found {len(numbers)} numbers via bright container")
            
            # Strategy 3: Simple number count heuristic
            if not bright_numbers:
                all_numbers_on_page = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', html_content)
                unique_numbers = set(all_numbers_on_page)
                
                # If we have a small subset of numbers (not the full 1-80), they might be the bright ones
                if 1 <= len(unique_numbers) <= 15:
                    for num in unique_numbers:
                        bright_numbers.add(int(num))
                    logger.info(f"Found {len(unique_numbers)} numbers via count heuristic")
            
            logger.info(f"Detection complete. Found {len(bright_numbers)} numbers: {sorted(bright_numbers)}")
            return bright_numbers
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return set()
    
    async def send_telegram_alert(self, numbers, message_type="bright"):
        """Send alert via Telegram"""
        if not numbers:
            return
        
        if message_type == "bright":
            message = f"🚨 **KENO BRIGHT NUMBERS DETECTED!** 🚨\n"
            message += f"🎯 Numbers: **{sorted(numbers)}**\n"
            message += f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🔗 Monitor: FlashSport Keno"
        else:
            message = f"📊 **Keno Monitor Status**\n"
            message += f"✅ System is running\n"
            message += f"⏰ Last check: {time.strftime('%H:%M:%S')}\n"
            message += f"🔍 Last detected: {sorted(numbers) if numbers else 'None'}"
        
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
        """Perform one check cycle"""
        logger.info("Checking for bright numbers...")
        
        html_content = self.fetch_website_content()
        if html_content:
            current_numbers = self.detect_bright_numbers(html_content)
            
            # Only alert if we found some numbers (not empty)
            if current_numbers and current_numbers != self.last_detected_numbers:
                logger.info(f"New numbers detected: {current_numbers}")
                await self.send_telegram_alert(current_numbers, "bright")
                self.last_detected_numbers = current_numbers
            else:
                logger.info("No new numbers detected in this check")
        else:
            logger.warning("Failed to fetch website content")
    
    async def send_status_update(self):
        """Send periodic status update"""
        html_content = self.fetch_website_content()
        current_numbers = self.detect_bright_numbers(html_content) if html_content else set()
        await self.send_telegram_alert(current_numbers, "status")

# Create monitor instance
monitor = KenoCloudMonitor()

async def main_check():
    """Main check function"""
    await monitor.check_and_alert()

def run_async_check():
    """Run the async check in event loop"""
    asyncio.run(main_check())

def start_monitor():
    """Start the monitoring scheduler"""
    if not monitor.telegram_token or not monitor.chat_id:
        logger.error("Cannot start monitor - missing Telegram credentials")
        return
        
    logger.info("Starting Keno Cloud Monitor...")
    
    # Initial status message
    try:
        asyncio.run(monitor.send_status_update())
    except Exception as e:
        logger.error(f"Failed to send initial status: {e}")
    
    # Set up scheduler - check every 10 seconds
    schedule.every(10).seconds.do(run_async_check)
    
    # Send status update every 30 minutes
    schedule.every(30).minutes.do(lambda: asyncio.run(monitor.send_status_update()))
    
    # Run scheduler continuously
    while True:
        schedule.run_pending()
        time.sleep(1)

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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎰 Keno Bright Numbers Monitor</h1>
                <div class="status">✅ System is running and monitoring FlashSport Keno</div>
                
                <div class="info">
                    <p><strong>Monitoring:</strong> https://flashsport.bet/</p>
                    <p><strong>Check Interval:</strong> Every 10 seconds</p>
                    <p><strong>Status:</strong> <span id="status">Active</span></p>
                    <p><strong>Last Check:</strong> <span id="time">""" + time.strftime('%Y-%m-%d %H:%M:%S') + """</span></p>
                </div>
                
                <p>This service automatically detects when numbers brighten up in FlashSport Keno and sends instant Telegram notifications.</p>
                
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
        "check_interval": "10 seconds"
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "monitoring": "flashsport.bet/keno",
        "check_interval": "10 seconds",
        "uptime": "24/7"
    })

def start_monitor_thread():
    """Start the monitor in a separate thread"""
    monitor_thread = threading.Thread(target=start_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    logger.info("Monitor thread started")

if __name__ == "__main__":
    # Start the monitor in a separate thread
    start_monitor_thread()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
