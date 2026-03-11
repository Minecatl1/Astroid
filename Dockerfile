FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/Bot/ ./

# Default to the Stoat bridge service. Override with BOT_SCRIPT if needed.
ENV BOT_SCRIPT=stoat_bridge.py

CMD ["sh", "-c", "python ${BOT_SCRIPT}"]
