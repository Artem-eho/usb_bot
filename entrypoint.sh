#!/bin/bash
set -e

# Start nginx in the background
nginx -g 'daemon off;' &
NGINX_PID=$!

# Start the bot in the foreground
python3 -m bot &
BOT_PID=$!

# Handle signals — shut down both processes gracefully
trap "kill $BOT_PID $NGINX_PID 2>/dev/null; wait $BOT_PID $NGINX_PID 2>/dev/null" SIGINT SIGTERM

# Wait for either process to exit
wait -n $BOT_PID $NGINX_PID
EXIT_CODE=$?

# If one exits, stop the other
kill $BOT_PID $NGINX_PID 2>/dev/null || true
wait $BOT_PID $NGINX_PID 2>/dev/null || true

exit $EXIT_CODE
