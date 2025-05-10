from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import requests
import re
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

# ======== CONFIGURATION ========
# Telegram settings - REPLACE WITH YOUR VALUES
TELEGRAM_BOT_TOKEN = "8092208949:AAHsHcBUJ9AGFD2h34qiHbGek6pR4mf99Zo"  # Get this from BotFather
TELEGRAM_CHAT_ID = "-1002552787335"  # Replace with your group's numerical ID (not the URL)

# Chrome driver settings
RUN_HEADLESS = True  # Set to False if you want to see the browser window
DELAY_SECONDS = 2  # Delay between page loads
SAVE_IMAGES_LOCALLY = True  # Set to False if you don't want to save images locally
DEFAULT_IMAGE_PATH = "default_course_image.jpg"  # Path to a default course image if download fails
MAX_WORKERS = 3  # Number of parallel threads
MAX_RETRIES = 2  # Maximum number of retries for failed operations
PAGE_LOAD_TIMEOUT = 15  # Reduced from 30 to 15 seconds
# ==============================

# Set up browser for GitHub Actions or local use
options = Options()

if os.getenv('GITHUB_ACTIONS') == 'true':  # Detect GitHub Actions environment
    print("🛠️ Running in GitHub Actions (Headless Chrome Mode)")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
else:  # Local development
    print("💻 Running locally with custom browser settings")
    options.headless = RUN_HEADLESS
    # No need for binary_location unless you're using a non-standard Chrome location

# Create a folder for saving images
if SAVE_IMAGES_LOCALLY and not os.path.exists("course_images"):
    os.makedirs("course_images")

# Create a default course image if it doesn't exist
def create_default_image():
    if not os.path.exists(DEFAULT_IMAGE_PATH):
        try:
            # First try to install Pillow if not available
            import importlib
            try:
                importlib.import_module('PIL')
            except ImportError:
                print("Installing Pillow module...")
                import subprocess
                subprocess.check_call(['pip', 'install', 'Pillow'])

            # Now create the image
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (800, 450), color=(53, 121, 246))
            d = ImageDraw.Draw(img)
            d.rectangle([(50, 50), (750, 400)], outline=(255, 255, 255), width=5)
            img.save(DEFAULT_IMAGE_PATH)
            print(f"Created default image at {DEFAULT_IMAGE_PATH}")
        except Exception as e:
            print(f"Could not create default image: {e}")
            # Create a simple text file as fallback
            with open(DEFAULT_IMAGE_PATH, 'w') as f:
                f.write("Default image fallback")
            print(f"Created fallback placeholder at {DEFAULT_IMAGE_PATH}")

# Helper function to check if image URL is a data URL
def is_data_url(url):
    return url.startswith('data:')

# Helper function to send Telegram messages to group
async def send_to_telegram_group(message, image_path=None):
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        # Debug info
        print(f"Sending to group ID: {TELEGRAM_CHAT_ID}")

        # Check if the image exists before attempting to send
        has_valid_image = image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 100

        if has_valid_image:
            with open(image_path, 'rb') as photo:
                await bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=photo,
                    caption=message,
                    parse_mode='HTML'
                )
                print(f"✅ Sent message with photo to Telegram group")
        else:
            # If no image or image doesn't exist, send text message
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            print(f"✅ Sent text message to Telegram group")

        return True
    except TelegramError as te:
        print(f"❌ Telegram Error: {te}")
        if "Chat not found" in str(te):
            print("Make sure the bot is added to the group and has permission to send messages")
            print("Check that you're using the numerical chat ID, not the username")
        elif "Bot was blocked by the user" in str(te):
            print("The bot was blocked by the user or group")
        return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        print(f"Message was: {message[:100]}...")
        if image_path:
            print(f"Image path was: {image_path}")
        return False

# Extract coupon code from URL or page
def extract_coupon_code(driver, url):
    if not url:
        return None
        
    # Try to extract from URL first
    coupon_patterns = [
        r'couponCode=([A-Z0-9]+)',
        r'coupon=([A-Z0-9]+)',
        r'code=([A-Z0-9]+)',
        r'promo=([A-Z0-9]+)',
        r'promocode=([A-Z0-9]+)'
    ]

    for pattern in coupon_patterns:
        url_match = re.search(pattern, url, re.IGNORECASE)
        if url_match:
            coupon_code = url_match.group(1)
            print(f"✅ Found coupon code in URL: {coupon_code}")
            return coupon_code

    # If not in URL, try to find on page
    try:
        # Look for elements that might contain coupon info
        potential_texts = []

        # Method 1: Look for elements with coupon-related text
        coupon_elements = driver.find_elements(By.XPATH,
            "//*[contains(text(), 'coupon') or contains(text(), 'COUPON') or contains(text(), 'Coupon') or " +
            "contains(text(), 'code') or contains(text(), 'CODE') or contains(text(), 'promo') or " +
            "contains(text(), 'PROMO') or contains(text(), 'discount') or contains(text(), 'DISCOUNT')]")

        for element in coupon_elements:
            try:
                text = element.text.strip()
                if text:
                    potential_texts.append(text)
                    # Also check parent element
                    parent = element.find_element(By.XPATH, "./..")
                    parent_text = parent.text.strip()
                    if parent_text and parent_text != text:
                        potential_texts.append(parent_text)
            except:
                continue

        # Process all potential texts
        for text in potential_texts:
            # Look for patterns like "CODE: ABCDEF" or "Coupon: ABCDEF"
            pattern_matches = re.search(r'(?:code|coupon|promo)[:\s]+([A-Z0-9]{5,})', text, re.IGNORECASE)
            if pattern_matches:
                coupon_code = pattern_matches.group(1)
                print(f"✅ Found coupon code in text: {coupon_code}")
                return coupon_code

            # Otherwise look for any sequence that looks like a coupon code
            code_match = re.search(r'[A-Z0-9]{5,}', text)
            if code_match:
                coupon_code = code_match.group(0)
                print(f"✅ Found potential coupon code: {coupon_code}")
                return coupon_code

    except Exception as e:
        print(f"❌ Error extracting coupon code from page: {e}")

    return None

def get_udemy_link_with_coupon(driver):
    try:
        # List of possible selectors for the Udemy link
        selectors = [
            '//a[contains(text(), "APPLY HERE")]',
            '//a[contains(@class, "wp-block-button__link")]',
            '//a[contains(@class, "button")]',
            '//a[contains(@href, "udemy.com")]',
            '//a[contains(@class, "has-luminous-vivid-amber")]',
            '//a[contains(@class, "elementor-button")]',
            '//a[contains(@class, "btn")]',
            '//a[contains(@class, "course-link")]',
            '//a[contains(@class, "enroll-button")]',
            '//a[contains(@class, "get-course")]'
        ]

        # Try each selector with explicit wait
        wait = WebDriverWait(driver, 10)
        for selector in selectors:
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                href = element.get_attribute("href")
                if href and 'udemy.com' in href:
                    print(f"✅ Found Udemy link using selector: {selector}")
                    return href
            except:
                continue

        # If no link found with selectors, try finding any Udemy link on the page
        print("Trying to find any Udemy link on the page...")
        links = driver.find_elements(By.TAG_NAME, 'a')
        for link in links:
            try:
                href = link.get_attribute('href')
                if href and 'udemy.com' in href:
                    print(f"✅ Found Udemy link from page links: {href}")
                    return href
            except:
                continue

        # If still no link found, try JavaScript to find links
        print("Trying JavaScript method to find Udemy links...")
        js_script = """
        return Array.from(document.getElementsByTagName('a'))
            .map(a => a.href)
            .filter(href => href && href.includes('udemy.com'));
        """
        udemy_links = driver.execute_script(js_script)
        if udemy_links and len(udemy_links) > 0:
            print(f"✅ Found Udemy link using JavaScript: {udemy_links[0]}")
            return udemy_links[0]

        print("❌ Could not find any Udemy link on the page")
        return None

    except Exception as e:
        print(f"❌ Error in get_udemy_link_with_coupon: {e}")
        return None

# Function to test Telegram connection
async def test_telegram_connection():
    print("Testing Telegram connection...")
    test_message = f"🧪 Testing Telegram connection - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    success = await send_to_telegram_group(test_message)

    if success:
        print("✅ Telegram connection test successful!")
    else:
        print("❌ Telegram connection test failed!")
        print("Please check your bot token and group ID.")
        print("Make sure the bot is added to the group and has permission to send messages.")

    return success

# Main function to run the asynchronous Telegram operations
async def run_telegram_operations(messages_with_images):
    print(f"Sending {len(messages_with_images)} messages to Telegram group...")

    # First test the connection
    connection_ok = await test_telegram_connection()
    if not connection_ok:
        print("Skipping sending messages due to connection issues.")
        return

    success_count = 0
    failure_count = 0

    for msg, img_path in messages_with_images:
        success = await send_to_telegram_group(msg, img_path)
        if success:
            success_count += 1
            await asyncio.sleep(2)  # Add delay between messages to avoid rate limits
        else:
            failure_count += 1
            await asyncio.sleep(5)  # Longer delay if there was an error

    print(f"Messages sent: {success_count}, Failed: {failure_count}")

def get_course_description(driver):
    try:
        desc_elements = driver.find_elements(By.CSS_SELECTOR, ".td-post-content p")
        for i, p in enumerate(desc_elements):
            if i < 3:  # Only get first 3 paragraphs
                text = p.text.strip()
                if text and len(text) > 20:  # Only meaningful paragraphs
                    description = text
                    # Trim to reasonable length
                    if len(description) > 200:
                        description = description[:197] + "..."
                    return f"📝 <i>{description}</i>\n\n"
    except Exception as e:
        print(f"Error getting course description: {e}")
    return ""

def process_course(args):
    """Process a single course in a separate thread"""
    title, link, img_url, index = args
    driver = None
    try:
        # Create a new driver instance for this thread
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_argument('--headless')  # Run in headless mode for speed
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        print(f"\nProcessing course: {title}")
        driver.get(link)
        time.sleep(DELAY_SECONDS)

        # Get Udemy link with coupon
        udemy_link = get_udemy_link_with_coupon(driver)
        if not udemy_link:
            print(f"Could not find Udemy link for course: {title}")
            return None

        # Extract coupon code
        coupon_code = extract_coupon_code(driver, udemy_link)
        coupon_text = f"🎟️ <b>Coupon Code:</b> <code>{coupon_code}</code>\n" if coupon_code else ""

        # Get course description
        description = get_course_description(driver)

        # Download image if available
        image_path = None
        if img_url and not is_data_url(img_url):
            try:
                response = requests.get(img_url, timeout=5)  # Reduced timeout
                if response.status_code == 200:
                    image_path = f"course_images/course_{index}.jpg"
                    with open(image_path, 'wb') as f:
                        f.write(response.content)
            except Exception as e:
                print(f"Error downloading image: {e}")
                image_path = DEFAULT_IMAGE_PATH

        # Format message for Telegram
        message = (
            f"🔥 <b>{title}</b>\n\n"
            f"{description}"
            f"🌐 <a href='{udemy_link}'>Enroll Now (Free)</a>\n"
            f"{coupon_text}"
            f"📢 Share with friends who want to learn!\n\n"
            f"#FreeCourse #Udemy #OnlineLearning"
        )

        print(f"✅ Course processed successfully: {title}")
        return (message, image_path)

    except Exception as e:
        print(f"❌ Error processing course {title}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def scrape_free_courses():
    # Create default image for fallback
    create_default_image()

    # Initialize main WebDriver
    try:
        print("Initializing Chrome WebDriver...")
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    except Exception as e:
        print(f"❌ WebDriver initialization failed: {e}")
        raise

    telegram_messages = []

    try:
        # Open CourseJoiner "Free Udemy" page
        url = "https://www.coursejoiner.com/category/free-udemy/"
        print(f"Opening {url}...")
        
        try:
            driver.get(url)
            time.sleep(DELAY_SECONDS)
        except Exception as e:
            print(f"❌ Error accessing website: {e}")
            error_message = f"⚠️ <b>Error accessing CourseJoiner</b>\n\nCould not access the website. Please try again later."
            telegram_messages.append((error_message, None))
            return

        # Get current date for reporting
        current_date = datetime.now().strftime("%Y-%m-%d")
        summary_message = f"🔥 <b>FREE UDEMY COURSES</b> - {current_date} 🔥\n\n<i>Finding the latest free courses for you...</i>"
        telegram_messages.append((summary_message, None))

        # Wait for content to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "td-block-span6")))
        time.sleep(2)  # Additional small wait to ensure content is fully loaded

        # Find all course blocks with optimized selectors
        print("Looking for course blocks...")
        blocks = driver.find_elements(By.CSS_SELECTOR, ".td-block-span6")
        if not blocks:
            print("Trying alternative selector...")
            blocks = driver.find_elements(By.CSS_SELECTOR, ".td_module_wrap")
        
        print(f"Found {len(blocks)} course blocks")

        if not blocks:
            error_message = f"⚠️ <b>No Courses Found</b>\n\nCould not find any courses at this time. Please try again later."
            telegram_messages.append((error_message, None))
            return

        # Extract course information
        course_data = []
        for i, block in enumerate(blocks):
            try:
                # Try multiple selectors for title and link
                title_element = None
                for selector in ["h3.entry-title a", "h3 a", ".entry-title a", "a"]:
                    try:
                        elements = block.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            title_element = elements[0]
                            break
                    except:
                        continue

                if not title_element:
                    print(f"Could not find title element in block {i}")
                    continue

                title = title_element.text.strip()
                if not title:
                    print(f"Empty title in block {i}")
                    continue

                link = title_element.get_attribute("href")
                if not link:
                    print(f"No link found for course: {title}")
                    continue

                # Get course image
                img_url = None
                for img_selector in ["img.entry-thumb", "img", ".entry-thumb"]:
                    try:
                        img_elements = block.find_elements(By.CSS_SELECTOR, img_selector)
                        if img_elements:
                            img_url = img_elements[0].get_attribute("src")
                            break
                    except:
                        continue

                if title and link:
                    course_data.append((title, link, img_url, i))
                    print(f"✅ Found course {i+1}: {title}")
            except Exception as e:
                print(f"❌ Error processing block {i}: {e}")
                continue

        print(f"Successfully extracted {len(course_data)} courses")

        if not course_data:
            error_message = f"⚠️ <b>No Courses Found</b>\n\nCould not find any valid courses at this time. Please try again later."
            telegram_messages.append((error_message, None))
            return

        # Process courses in parallel
        successful_courses = 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(process_course, course_data))

        # Filter out None results and add successful courses to messages
        for result in results:
            if result:
                telegram_messages.append(result)
                successful_courses += 1

        # Final summary message
        if successful_courses > 0:
            summary = f"✅ <b>Today's Free Courses Update</b>\n\nJust shared {successful_courses} free Udemy courses! Grab them while they last.\n\n#FreeUdemy #CourseUpdate"
            telegram_messages.append((summary, None))
        else:
            error_message = f"⚠️ <b>No Courses Found</b>\n\nCould not find any courses at this time. Please try again later."
            telegram_messages.append((error_message, None))

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        error_message = f"⚠️ <b>Error During Scraping</b>\n\nAn error occurred while scraping courses. Please try again later."
        telegram_messages.append((error_message, None))
    finally:
        driver.quit()
        print("Browser closed.")

    return telegram_messages

# Helper function to extract chat ID from URL or handle
def get_chat_id():
    if TELEGRAM_CHAT_ID.startswith('-100'):
        # Already in the right format
        return TELEGRAM_CHAT_ID

    # If it's a URL like https://t.me/username
    if TELEGRAM_CHAT_ID.startswith('https://t.me/'):
        username = TELEGRAM_CHAT_ID.split('/')[-1]
        print(f"⚠️ Using chat username: @{username}")
        print("⚠️ Note: Using a username instead of a chat ID may cause issues.")
        print("⚠️ It's recommended to use the numerical chat ID instead.")
        return username

    # If it starts with @ or is just the username
    if TELEGRAM_CHAT_ID.startswith('@'):
        print(f"⚠️ Using chat username: {TELEGRAM_CHAT_ID}")
        print("⚠️ Note: Using a username instead of a chat ID may cause issues.")
        print("⚠️ It's recommended to use the numerical chat ID instead.")
        return TELEGRAM_CHAT_ID

    # Otherwise, assume it's already a chat ID
    return TELEGRAM_CHAT_ID

# Add this at the end of the file, just before the if __name__ == "__main__" block

async def main():
    print("Starting Free Udemy Course Telegram Bot...")
    
    # Check if Python Telegram Bot is installed
    try:
        from telegram import Bot
    except ImportError:
        print("Installing python-telegram-bot...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'python-telegram-bot'])
        from telegram import Bot

    # Check configuration
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("⚠️ ERROR: Please set your Telegram bot token in the script!")
        print("Get your bot token from @BotFather")
        return

    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "YOUR_GROUP_ID":
        print("⚠️ ERROR: Please set your Telegram group ID in the script!")
        print("Add the bot to your group with admin privileges")
        return

    try:
        # Update the chat ID
        TELEGRAM_CHAT_ID = get_chat_id()

        # Run the scraper
        print("Starting course scraping...")
        telegram_messages = scrape_free_courses()
        
        # Send messages to Telegram
        if telegram_messages:
            print(f"\nSending {len(telegram_messages)} messages to Telegram group...")
            await run_telegram_operations(telegram_messages)
        else:
            print("No courses found to send.")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        print("Please check your configuration and try again.")

# Update the main execution block
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        print("Please check your configuration and try again.")