#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.12 --allow-existing .build_venv || uv venv --allow-existing .build_venv
  source .build_venv/bin/activate
  uv pip install -r requirements.txt
  python manage.py collectstatic --noinput --clear
  python manage.py migrate --noinput || true
else
  python3 -m pip install -r requirements.txt --break-system-packages || python3 -m pip install -r requirements.txt
  python3 manage.py collectstatic --noinput --clear
  python3 manage.py migrate --noinput || true
fi
