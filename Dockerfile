# Aravix bot — Docker image for Render.
# ffmpeg/ffprobe are runtime binaries the music cog shells out to via
# discord.FFmpegPCMAudio (bare "ffmpeg" resolved from PATH), so they are
# installed with apt — pip cannot provide them.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
