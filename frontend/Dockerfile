FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8765

CMD ["python", "run_frontend.py", "run", "app.py", "--host=0.0.0.0", "--port=8765"]
