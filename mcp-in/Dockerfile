FROM python:3.12-slim

RUN pip install --no-cache-dir mcp httpx

WORKDIR /app
COPY . .

EXPOSE 8300

CMD ["python", "main.py"]
