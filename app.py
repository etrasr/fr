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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KenoCloudMonitor:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
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
        Advanced detection without relying on specific CSS classes
        """
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bright_numbers = set()
            
            # Strategy 1: Find all numbers on the page
            all_numbers = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', html_content)
            number_count = len(set(all_numbers))
            
            # If we have a small subset of numbers (not the full 1-80), they're likely the bright preview
            if 1 <= number_count <= 15:
                for num in all_numbers:
                    bright_numbers.add(int(num))
                return bright_numbers
            
            # Strategy 2: Look for numbers in specific containers that might be preview
            preview_indicators = [
                'preview', 'next', 'upcoming', 'live', 'current', 
                'highlight', 'keno', 'game', 'draw', 'result'
            ]
            
            # Check all elements for preview indicators
            for element in soup.find_all():
                element_classes = ' '.join(element.get('class', []))
                element_id = element.get('id', '')
                element_text = element.get_text().strip()
                
                # If element has preview-related classes/ids
                container_info = element_classes + ' ' + element_id
                if any(indicator in container_info.lower() for indicator in preview_indicators):
                    numbers_in_element = re.findall(r'\b([1-9]|[1-7][0-9]|80)\b', element_text)
                    for num in numbers_in_element:
                        bright_numbers.add(int(num))
            
            # Strategy 3: Look for the most recently added numbers (common pattern)
            # Many sites add preview numbers dynamically with JavaScript
            # We look for numbers that appear in specific patterns
            
            # Remove common false positives
            if bright_numbers:
                # If we detected almost all numbers, it's probably the main grid
                if len(bright_numbers) > 20:
                    bright_numbers = set()
            
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
    logger.info("Starting Keno Cloud Monitor...")
    
    # Initial status message
    asyncio.run(monitor.send_status_update())
    
    # Set up scheduler - check every 5 seconds
    schedule.every(5).seconds.do(run_async_check)
    
    # Send status update every 30 minutes
    schedule.every(30).minutes.do(lambda: asyncio.run(monitor.send_status_update()))
    
    # Run scheduler continuously
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start monitor in a separate thread
def start_monitor_thread():
    monitor_thread = threading.Thread(target=start_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
