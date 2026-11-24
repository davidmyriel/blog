FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py server.py ./

# Railway sets PORT; server.py defaults to 7860 when it isn't set.
CMD ["python", "server.py"]
