FROM python:3.11-slim

# Install ffmpeg (needed by yt-dlp to merge video+audio on some sites)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/tmp/jobs /app/data

CMD ["python", "bot.py"]
