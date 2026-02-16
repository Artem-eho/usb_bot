#!/bin/sh

# Start nginx as daemon (background)
nginx

# Run the bot in foreground (PID 1, receives signals)
exec python3 -m bot
