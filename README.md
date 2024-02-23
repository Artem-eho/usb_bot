# wrshp_bot

Телеграмм бот для скачивания файлов из директории MOUNT_PATH

```
DIR=usb_bot 
mkdir $DIR && cd $DIR && mkdir USB
cat <<EOF > .env
TELEGRAM_TOKEN=<CHANGE_ME>
TELEGRAM_CHAT_ID=<CHANGE_ME>
MOUNT_PATH=USB
FILTERED_USERS=<CHANGE_ME>
EOF
docker run -d --name usb_bot --env-file=.env -v ./USB:/app/USB artemeho/usb_bot
```
