#!/bin/sh
set -e
chmod 600 /bot/user-config.py 2>/dev/null || true
chmod 600 /bot/user-password.py 2>/dev/null || true
exec "$@"
