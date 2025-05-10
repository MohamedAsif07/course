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

# ======== CONFIGURATION ========
# Telegram settings - REPLACE WITH YOUR VALUES
TELEGRAM_BOT_TOKEN = "8092208949:AAHsHcBUJ9AGFD2h34qiHbGek6pR4mf99Zo"  # Get this from BotFather
TELEGRAM_CHAT_ID = "-1002552787335"  # Replace with your group's numerical ID (not the URL)

# Chrome driver settings
RUN_HEADLESS = True  # Set to False if you want to see the browser window
DELAY_SECONDS = 3  # Delay between page loads
SAVE_IMAGES_LOCALLY = True  # Set to False if you don't want to save images locally
DEFAULT_IMAGE_PATH = "default_course_image.jpg"  # Path to a default course image if download fails
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
    # Try to extract from URL first
    coupon_patterns = [
        r'couponCode=([A-Z0-9]+)',
        r'coupon=([A-Z0-9]+)'
    ]

    for pattern in coupon_patterns:
        url_match = re.search(pattern, url, re.IGNORECASE)
        if url_match:
            return url_match.group(1)

    # If not in URL, try to find on page
    try:
        # Look for elements that might contain coupon info
        potential_texts = []

        # Method 1: Look for elements with "coupon" text
        coupon_elements = driver.find_elements(By.XPATH,
                                               "//*[contains(text(), 'coupon') or contains(text(), 'COUPON') or contains(text(), 'Coupon') or contains(text(), 'code') or contains(text(), 'CODE')]")

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
            pattern_matches = re.search(r'(?:code|coupon)[:\s]+([A-Z0-9]{5,})', text, re.IGNORECASE)
            if pattern_matches:
                return pattern_matches.group(1)

            # Otherwise look for any sequence that looks like a coupon code
            code_match = re.search(r'[A-Z0-9]{5,}', text)
            if code_match:
                return code_match.group(0)
    except:
        pass

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

# Main scraping function
def scrape_free_courses():
    # Create default image for fallback
    create_default_image()

    # Initialize WebDriver - proper way to use Chrome driver
    try:
        print("Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except Exception as e:
        print(f"❌ WebDriver initialization failed: {e}")
        raise

    # For storing messages to send to Telegram
    telegram_messages = []

    try:
        # Open CourseJoiner "Free Udemy" page
        url = "https://www.coursejoiner.com/category/free-udemy/"
        print(f"Opening {url}...")
        driver.get(url)
        time.sleep(DELAY_SECONDS)

        # Get current date for reporting
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Send initial report to Telegram
        summary_message = f"🔥 <b>FREE UDEMY COURSES</b> - {current_date} 🔥\n\n<i>Finding the latest free courses for you...</i>"
        telegram_messages.append((summary_message, None))

        # Find all course blocks
        blocks = driver.find_elements(By.CLASS_NAME, "td-block-span6")

        # Store course info
        course_titles = []
        course_links = []
        image_urls = []

        # Extract initial course information
        print("Extracting course information...")
        for block in blocks:
            try:
                title = block.find_element(By.TAG_NAME, "h3").text
                link = block.find_element(By.TAG_NAME, "a").get_attribute("href")

                # Get image URL
                img = block.find_element(By.CLASS_NAME, "entry-thumb")
                img_url = img.get_attribute("src")

                course_titles.append(title)
                course_links.append(link)
                image_urls.append(img_url)

            except Exception as e:
                print(f"Error extracting course info: {e}")
                continue

        total_courses = len(course_titles)
        print(f"Found {total_courses} courses in total")

        # Process each course - limit to first 10 for testing
        successful_courses = 0
        max_courses = min(10, total_courses)  # Process at most 10 courses for initial test

        for i, (title, course_url, img_url) in enumerate(
                zip(course_titles[:max_courses], course_links[:max_courses], image_urls[:max_courses])):
            try:
                print(f"\nProcessing course {i + 1}/{max_courses}: {title}")

                # Format title for filename
                safe_title = ''.join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in title)
                safe_title = safe_title[:50]

                # Image path for local saving and Telegram
                img_path = None

                # Handle image download
                if SAVE_IMAGES_LOCALLY:
                    img_path = f"course_images/{i + 1}_{safe_title}.jpg"

                    # Check if image URL is a data URL
                    if is_data_url(img_url):
                        print(f"⚠️ Skipping data URL image, using default instead")
                        img_path = DEFAULT_IMAGE_PATH
                    else:
                        # Download the image
                        try:
                            response = requests.get(img_url, timeout=10)
                            if response.status_code == 200:
                                with open(img_path, 'wb') as f:
                                    f.write(response.content)
                                print(f"✅ Image saved to {img_path}")
                            else:
                                print(f"❌ Failed to download image (Status code: {response.status_code})")
                                img_path = DEFAULT_IMAGE_PATH
                        except Exception as e:
                            print(f"❌ Error downloading image: {e}")
                            img_path = DEFAULT_IMAGE_PATH

                # Visit course page to get Udemy link and possible coupon
                driver.get(course_url)
                time.sleep(DELAY_SECONDS)

                # Find "APPLY HERE" button and extract the Udemy link
                udemy_link = None
                try:
                    wait = WebDriverWait(driver, 10)
                    apply_button = wait.until(
                        EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "APPLY HERE")]')))
                    udemy_link = apply_button.get_attribute("href")
                except:
                    print("❌ Could not find APPLY HERE button, trying alternatives...")
                    # Try alternative methods to find the link
                    try:
                        links = driver.find_elements(By.TAG_NAME, 'a')
                        for link in links:
                            href = link.get_attribute('href')
                            if href and 'udemy.com' in href:
                                udemy_link = href
                                break
                        else:
                            raise Exception("No Udemy link found")
                    except Exception as e:
                        print(f"❌ Could not find Udemy link: {e}")
                        continue

                # Extract coupon code
                coupon_code = extract_coupon_code(driver, udemy_link)
                coupon_text = f"🎟️ <b>Coupon Code:</b> <code>{coupon_code}</code>\n" if coupon_code else ""

                # Get course description
                description = ""
                try:
                    desc_elements = driver.find_elements(By.CSS_SELECTOR, ".td-post-content p")
                    for i, p in enumerate(desc_elements):
                        if i < 3:  # Only get first 3 paragraphs
                            text = p.text.strip()
                            if text and len(text) > 20:  # Only meaningful paragraphs
                                description = text
                                break
                except:
                    pass

                # Format description
                if description:
                    # Trim to reasonable length
                    if len(description) > 200:
                        description = description[:197] + "..."
                    description = f"📝 <i>{description}</i>\n\n"

                # Format message for Telegram
                message = (
                    f"🔥 <b>{title}</b>\n\n"
                    f"{description}"
                    f"🌐 <a href='{udemy_link}'>Enroll Now (Free)</a>\n"
                    f"{coupon_text}"
                    f"📢 Share with friends who want to learn!\n\n"
                    f"#FreeCourse #Udemy #OnlineLearning"
                )

                # Add to queue for sending
                telegram_messages.append((message, img_path))
                successful_courses += 1

                print(f"✅ Course processed successfully")

            except Exception as e:
                print(f"❌ Error processing course: {e}")

        # Final summary message
        summary = f"✅ <b>Today's Free Courses Update</b>\n\nJust shared {successful_courses} free Udemy courses! Grab them while they last.\n\n#FreeUdemy #CourseUpdate"
        telegram_messages.append((summary, None))

        return telegram_messages

    finally:
        # Clean up
        driver.quit()
        print("Browser closed.")

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

# Main execution
if __name__ == "__main__":
    print("Starting Free Udemy Course Telegram Bot...")

    # Check if Python Telegram Bot is installed
    try:
        from telegram import Bot
    except ImportError:
        print("Installing python-telegram-bot...")
        import subprocess

        subprocess.check_call(['pip', 'install', 'python-telegram-bot'])
        # Re-import
        from telegram import Bot

    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or TELEGRAM_CHAT_ID == "YOUR_GROUP_ID":
        print("⚠️ ERROR: Please set your Telegram bot token and group ID in the script!")
        print("Get your bot token from @BotFather and add the bot to your group with admin privileges")
        exit(1)

    # Update the chat ID
    TELEGRAM_CHAT_ID = get_chat_id()

    # Run the scraper
    telegram_queue = scrape_free_courses()

    # Send all messages to Telegram
    if telegram_queue:
        print(f"\nSending {len(telegram_queue)} messages to Telegram group...")
        asyncio.run(run_telegram_operations(telegram_queue))
        print("✅ Done sending messages to Telegram group!")
    else:
        print("No messages to send to Telegram.")