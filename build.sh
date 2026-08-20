#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv pip install -r requirements.txt --system
else
  python3 -m pip install -r requirements.txt --break-system-packages || python3 -m pip install -r requirements.txt
fi

python3 manage.py collectstatic --noinput --clear
