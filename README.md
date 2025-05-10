# Automated Udemy Course Scraper

This project automatically scrapes free Udemy courses from CourseJoiner.com and sends them to a Telegram group. It runs twice daily (at 00:00 UTC and 12:00 UTC) using GitHub Actions.

## Features

- 🔄 Automatic scraping twice daily
- 🤖 Headless browser operation
- 📱 Telegram integration
- 🎯 Coupon code extraction
- 🖼️ Image handling with fallback options
- ⚡ Error handling and logging

## Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd <repo-name>
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Telegram**
   - Create a new bot using [@BotFather](https://t.me/botfather)
   - Add the bot to your target group
   - Get the group's chat ID (you can use [@RawDataBot](https://t.me/rawdatabot))

4. **Set up GitHub Secrets**
   Add these secrets to your GitHub repository:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather
   - `TELEGRAM_CHAT_ID`: Your group's chat ID

## Local Development

1. **Configure environment variables**
   Create a `.env` file with:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

2. **Run the scraper**
   ```bash
   python cource.py
   ```

## GitHub Actions

The scraper runs automatically twice daily using GitHub Actions. You can also trigger it manually from the Actions tab in your repository.

## Configuration

You can modify these settings in `cource.py`:
- `RUN_HEADLESS`: Set to `False` to see the browser window
- `DELAY_SECONDS`: Delay between page loads
- `SAVE_IMAGES_LOCALLY`: Whether to save course images locally

## Contributing

Feel free to submit issues and enhancement requests! 