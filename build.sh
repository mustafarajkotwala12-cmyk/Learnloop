#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.12 .build_venv || uv venv .build_venv
  source .build_venv/bin/activate
  uv pip install -r requirements.txt
  python manage.py collectstatic --noinput --clear
else
  python3 -m pip install -r requirements.txt --break-system-packages || python3 -m pip install -r requirements.txt
  python3 manage.py collectstatic --noinput --clear
fi
