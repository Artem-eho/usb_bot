FROM python:3.11.2-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
EXPOSE 8080
CMD ["python3", "-m", "bot"]
