# One image for all three backend programs. The same image runs as:
#   the API:        uvicorn main:app ...        (the default command at the bottom)
#   the price feed: python stream_prices.py     (docker-compose overrides the command)
#   the matcher:    python match_orders.py      (docker-compose overrides the command)
# Build it from the backend folder:  docker build -t trading-backend .
# (Dockerfiles only allow comments on their own lines, not at the end of an instruction.)

# Small official Python image; same version as CI.
FROM python:3.12-slim

# No .pyc files inside the container, and print() shows up in `docker logs` straight away.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Every command below runs inside /app.
WORKDIR /app

# Copy ONLY the package list first, so Docker can reuse this slow install step
# on later builds as long as requirements.txt hasn't changed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy your code (.dockerignore keeps .env and other junk out).
COPY . .

# Don't run as root: limits the damage if something ever goes wrong.
RUN useradd --create-home appuser
USER appuser

# The API listens here (documentation only; docker-compose does the actual wiring).
EXPOSE 8000

# Default command: run the API. 0.0.0.0 = accept connections from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
