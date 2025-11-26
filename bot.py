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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class KenoCloudMonitor:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.telegram_token or not self.chat_id:
            logger.error("Missing Telegram credentials")
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
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            self.session.headers.update(self.headers)
            self.session.timeout = 10
        except Exception as e:
            logger.error(f"Failed to initialize monitor: {e}")
            raise

    def fetch_website_content(self):
        """Fetch website content with comprehensive error handling"""
        try:
            url = f'https://flashsport.bet/?t={int(time.time()*1000)}'
            response = self.session.get(url, timeout=8)
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            logger.warning("Request timeout")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected fetch error: {e}")
            return None

    def detect_bright_numbers(self, html_content):
        """Detect bright numbers with multiple fallback strategies"""
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bright_numbers = set()
            
            # Strategy 1: Direct regex scanning (fastest)
            bright_patterns = [
                r'class="[^"]*(blink|flash|pulse|glowing|highlight|active)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'style="[^"]*(animation|blink|flash|glow)[^"]*"[^>]*>.*?(\d{1,2})<',
                r'<[^>]*(blink|flash|pulse)[^>]*>.*?(\d{1,2})<'
            ]
            
            for pattern in bright_patterns:
                try:
                    matches = re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        for group in match.groups():
                            if group and group.isdigit() and 1 <= int(group) <= 80:
                                bright_numbers.add(int(group))
                except:
                    continue
            
            # Strategy 2: BeautifulSoup scanning
            try:
                bright_selectors = [
                    '[class*="blink"]', '[class*="flash"]', '[class*="pulse"]',
                    '[class*="glowing"]', '[class*="highlight"]', '[class*="active"]',
                    '[style*="blink"]', '[style*="flash"]', '[style*="animation"]'
                ]
                
                for selector in bright_selectors:
                    try:
                        elements = soup.select(selector)
                        for element in elements:
                            text = element.get_text().strip()
                            if text.isdigit() and 1 <= int(text) <= 80:
                                bright_numbers.add(int(text))
                    except:
                        continue
            except:
                pass
            
            # Filter false positives
            if len(bright_numbers) > 15:
                return set()
            
            if (bright_numbers and 
                min(bright_numbers) == 1 and 
                max(bright_numbers) >= 10 and 
                len(bright_numbers) >= 8):
                return set()
            
            return bright_numbers
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return set()

    async def send_telegram_alert(self, numbers, message_type="bright"):
        """Send alert with comprehensive error handling"""
        if not numbers and message_type == "bright":
            return
        
        current_time = time.time()
        
        if message_type == "bright" and (current_time - self.last_alert_time) < self.alert_cooldown:
            return
        
        try:
            if message_type == "bright":
                message = f"🚨 **KENO BRIGHT NUMBERS!** 🚨\n🎯 **{sorted(numbers)}**\n⏰ {time.strftime('%H:%M:%S')}"
                self.last_alert_time = current_time
            else:
                message = f"📊 **Monitor Status**\n✅ System running\n⏰ {time.strftime('%H:%M:%S')}\n⚡ Every 2-3 seconds"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            if message_type == "bright":
                logger.info(f"Alert sent: {numbers}")
            else:
                logger.info("Status update sent")
                
        except Exception as e:
            logger.error(f"Telegram error: {e}")

    async def single_check(self):
        """Perform a single check with full error protection"""
        try:
            html_content = self.fetch_website_content()
            if html_content:
                current_numbers = self.detect_bright_numbers(html_content)
                
                if (current_numbers and 
                    current_numbers != self.last_detected_numbers and
                    1 <= len(current_numbers) <= 15):
                    
                    logger.info(f"BRIGHT NUMBERS: {current_numbers}")
                    await self.send_telegram_alert(current_numbers, "bright")
                    self.last_detected_numbers = current_numbers
                    
        except Exception as e:
            logger.error(f"Check error: {e}")

# Global monitoring state
monitor_state = {
    "active": True,
    "restart_count": 0,
    "last_restart": time.time(),
    "total_checks": 0,
    "last_success": time.time()
}

async def super_robust_monitor():
    """Main monitor loop with ultimate crash protection"""
    logger.info("🛡️ Starting SUPER ROBUST monitor")
    
    check_count = 0
    error_count = 0
    max_errors = 50
    
    while monitor_state["active"] and error_count < max_errors:
        try:
            # Create new monitor instance for each major iteration
            monitor = KenoCloudMonitor()
            
            # Send startup message
            try:
                await monitor.send_telegram_alert(set(), "status")
            except:
                pass
            
            # Inner monitoring loop
            inner_errors = 0
            max_inner_errors = 10
            
            while (monitor_state["active"] and 
                   inner_errors < max_inner_errors and 
                   error_count < max_errors):
                
                try:
                    start_time = time.time()
                    await monitor.single_check()
                    
                    monitor_state["total_checks"] += 1
                    monitor_state["last_success"] = time.time()
                    check_count += 1
                    inner_errors = 0
                    error_count = 0  # Reset main error count on success
                    
                    # Send status every 50 checks
                    if check_count % 50 == 0:
                        try:
                            await monitor.send_telegram_alert(set(), "status")
                        except:
                            pass
                        check_count = 0
                    
                    # Calculate sleep time
                    processing_time = time.time() - start_time
                    sleep_time = max(1.0, 3.0 - processing_time)  # 2-3 second intervals
                    
                    await asyncio.sleep(sleep_time)
                    
                except Exception as e:
                    inner_errors += 1
                    error_count += 1
                    logger.error(f"Inner loop error {inner_errors}: {e}")
                    await asyncio.sleep(2)
            
            # If we're here, inner loop had issues
            logger.warning(f"Inner loop restarted after {inner_errors} errors")
            await asyncio.sleep(5)
            
        except Exception as e:
            error_count += 1
            monitor_state["restart_count"] += 1
            logger.error(f"Outer loop error {error_count}: {e}")
            await asyncio.sleep(10)
    
    # If we exit the main loop, it's a critical failure
    logger.error(f"CRITICAL: Monitor stopped after {error_count} errors")

def never_die_monitor():
    """ULTIMATE protection - this function never returns"""
    while True:
        try:
            logger.info("🎯 STARTING MONITOR - ULTIMATE MODE")
            
            # Run the monitor with a timeout
            asyncio.run(super_robust_monitor())
            
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            break
        except Exception as e:
            monitor_state["restart_count"] += 1
            monitor_state["last_restart"] = time.time()
            
            logger.critical(f"💀 CATASTROPHIC FAILURE - RESTARTING: {e}")
            logger.critical(traceback.format_exc())
            
            # Send critical alert if possible
            try:
                token = os.getenv('TELEGRAM_BOT_TOKEN')
                chat_id = os.getenv('TELEGRAM_CHAT_ID')
                if token and chat_id:
                    bot = telegram.Bot(token=token)
                    asyncio.run(bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 **MONITOR CRASHED** 🚨\n🔄 Auto-restarting...\n🔢 Restart count: {monitor_state['restart_count']}",
                        parse_mode='Markdown'
                    ))
            except:
                pass
            
            # Wait before restart
            time.sleep(15)
            
            # Force garbage collection and cleanup
            import gc
            gc.collect()
            
            logger.info("🔄 RESTARTING MONITOR...")

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
            <title>Keno Monitor - ULTIMATE</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .status {{ color: green; font-weight: bold; font-size: 18px; }}
                .info {{ margin: 20px 0; padding: 15px; background: #e8f4fd; border-radius: 5px; }}
                .ultimate {{ color: #ff4444; font-weight: bold; animation: pulse 1s infinite; }}
                @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} 100% {{ opacity: 1; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎰 Keno Monitor - ULTIMATE MODE</h1>
                <div class="status"><span class="ultimate">🔒 ULTIMATE CRASH PROTECTION ACTIVE</span></div>
                
                <div class="info">
                    <p><strong>Status:</strong> <span id="status">RUNNING</span></p>
                    <p><strong>Uptime:</strong> {hours}h {minutes}m</p>
                    <p><strong>Restarts:</strong> {monitor_state['restart_count']}</p>
                    <p><strong>Total Checks:</strong> {monitor_state['total_checks']}</p>
                    <p><strong>Check Interval:</strong> 2-3 seconds</p>
                    <p><strong>Last Success:</strong> <span id="lastSuccess">{time.strftime('%H:%M:%S', time.localtime(monitor_state['last_success']))}</span></p>
                </div>
                
                <p>This monitor has ULTIMATE crash protection and will run forever.</p>
                <p class="ultimate">⚡ Auto-restart on any failure • Never stops monitoring</p>
                
                <script>
                    function updateTime() {{
                        document.getElementById('lastSuccess').textContent = new Date().toLocaleString();
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
        "ultimate_mode": True,
        "restart_count": monitor_state["restart_count"],
        "total_checks": monitor_state["total_checks"],
        "uptime_seconds": time.time() - monitor_state["last_restart"],
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/monitor-status')
def monitor_status():
    return jsonify({
        "monitor_active": monitor_state["active"],
        "threads_alive": threading.active_count(),
        "restart_count": monitor_state["restart_count"],
        "total_checks": monitor_state["total_checks"],
        "last_success": monitor_state["last_success"],
        "python_version": sys.version
    })

def start_ultimate_monitor():
    """Start the ultimate never-die monitor"""
    monitor_thread = threading.Thread(target=never_die_monitor, name="UltimateMonitor")
    monitor_thread.daemon = False  # NOT daemon - we want it to keep running
    monitor_thread.start()
    logger.info("🎯 ULTIMATE MONITOR THREAD STARTED")

# Initialize and start everything
if __name__ == "__main__":
    logger.info("🚀 STARTING KENO MONITOR - ULTIMATE MODE")
    
    # Test environment variables
    if not os.getenv('TELEGRAM_BOT_TOKEN') or not os.getenv('TELEGRAM_CHAT_ID'):
        logger.error("❌ MISSING TELEGRAM CREDENTIALS")
        # Don't exit - maybe they'll be set later
    
    # Start the ultimate monitor
    start_ultimate_monitor()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Starting web server on port {port}")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.critical(f"Web server failed: {e}")
        # Keep the monitor running even if web server fails
        while True:
            time.sleep(60)
