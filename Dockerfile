FROM python:3.11.2-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt --no-cache-dir
COPY . .

COPY nginx.conf /etc/nginx/nginx.conf
RUN chmod +x entrypoint.sh

EXPOSE 8080
CMD ["./entrypoint.sh"]
