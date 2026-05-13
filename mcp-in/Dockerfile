FROM python:3.12-slim

RUN pip install --no-cache-dir mcp httpx

WORKDIR /app
COPY main.py .

EXPOSE 8300

CMD ["python", "main.py"]
