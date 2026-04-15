FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY data/ ./data/

RUN mkdir -p /app/credentials

EXPOSE 8000

# Default: token server. Agent worker overrides via Railway Custom Start Command.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
