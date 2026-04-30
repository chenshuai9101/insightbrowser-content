FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY . .

EXPOSE 7024
ENV PORT=7024
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7024"]
