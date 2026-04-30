FROM python:3.14-slim

WORKDIR /app

# Install Playwright + Crawlee + FastAPI
RUN pip install --no-cache-dir playwright \
    && playwright install chromium --with-deps \
    && pip install --no-cache-dir 'crawlee[playwright]' \
    && pip install --no-cache-dir fastapi uvicorn pydantic httpx

COPY main.py .
COPY routes/ routes/
COPY services/ services/

EXPOSE 7022
ENV PORT=7022
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7022"]
