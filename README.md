# 🎬 Telegram Video Downloader Bot

A simple Telegram bot that downloads videos from YouTube, Instagram, TikTok, Facebook, and 1000+ other sites. Just send a link → get your video!

## ✨ Features

- **One-step download** — send a link, get the video
- **Multi-platform** — YouTube, Instagram, TikTok, Facebook + 1000 more
- **Best quality** — downloads highest available quality
- **Rate limiting** — prevents abuse
- **Queue system** — handles multiple users simultaneously
- **Job logging** — SQLite analytics
- **Render-ready** — deploy in minutes

## 🚀 Deploy on Render (Recommended)

### Step 1: Get a Bot Token
1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`, follow prompts
3. Copy the token

### Step 2: Push to GitHub
```bash
git init
git add .
git commit -m "Video downloader bot"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 3: Deploy on Render
1. Go to [render.com](https://render.com) → New → **Background Worker**
2. Connect your GitHub repo
3. Render will auto-detect the `Dockerfile`
4. Add Environment Variable: `BOT_TOKEN` = your token
5. Click **Create Worker**
6. Done! Bot will be running in ~2 minutes

> **Note:** Use "Background Worker" (not "Web Service") since this bot uses polling, not webhooks.

## 💻 Run Locally

```bash
# 1. Clone and enter
git clone <your-repo>
cd telegram

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env → add your BOT_TOKEN

# 4. Run
python bot.py
```

**Requires:** Python 3.11+ and ffmpeg installed (for yt-dlp to merge video+audio on some sites).

## 🐳 Run with Docker

```bash
cp .env.example .env
# Edit .env → add your BOT_TOKEN
docker-compose up -d --build
```

## 🔧 Configuration

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token |
| `MAX_DURATION_SECONDS` | `600` | Max video duration (10 min) |
| `MAX_FILE_SIZE_MB` | `200` | Max download size |
| `TELEGRAM_UPLOAD_LIMIT_MB` | `50` | Telegram upload limit |
| `MAX_CONCURRENT_JOBS` | `3` | Parallel downloads |
| `RATE_LIMIT_PER_HOUR` | `10` | Per-user hourly limit |
| `JOB_TIMEOUT_SECONDS` | `300` | Download timeout |

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage instructions + limits |
| `/status` | Check current download |
| `/cancel` | Cancel running download |
| *(send a link)* | Downloads the video |

## 🗂 Project Structure

```
├── bot.py              # Entry point — handlers + download pipeline
├── downloader.py       # yt-dlp download module
├── queue_manager.py    # Async queue + rate limiting + SQLite logging
├── config.py           # .env loading and constants
├── models.py           # Data classes (Job, VideoMetadata)
├── utils.py            # URL detection, platform detection, helpers
├── .env.example        # Config template
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build
├── docker-compose.yml  # Local Docker deployment
├── render.yaml         # Render.com deployment config
└── README.md           # This file
```

## 📝 License

This project is provided as-is for personal use.
