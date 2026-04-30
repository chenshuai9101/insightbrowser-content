FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx

COPY main.py .
COPY app/ app/
COPY sdk.py .

EXPOSE 7000
ENV PORT=7000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000"]
