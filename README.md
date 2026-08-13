# LearnLoop

LearnLoop is a Django + Supabase-ready interactive learning platform. It has a
public activity catalogue, email/password accounts, optional Google OAuth via
django-allauth, separate teacher and student portals, a live six-character
class-code flow, JSON-powered activity builder, quiz player, and class results.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The demo command prints usable teacher and
student credentials plus the current live-session code.

## Supabase and Google OAuth

Copy `.env.example` to `.env` in your local environment manager and set
`SUPABASE_DB_URL` to Supabase's pooled PostgreSQL URL. Django owns the schema,
so run `python manage.py migrate` against the target database during release.

Google sign-in is wired through django-allauth. In Django admin, create a
`SocialApp` for the Google provider, add its client ID/secret, and attach it to
the configured Site. Then set the site's domain to the deployed Vercel domain
and add `/accounts/google/login/callback/` to Google Cloud's approved redirect
URIs.

## Deploy to Vercel

Set these Vercel environment variables:

- `DJANGO_SECRET_KEY`
- `SUPABASE_DB_URL`
- `DJANGO_ALLOWED_HOSTS` (for example `your-project.vercel.app`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` (for example `https://your-project.vercel.app`)
- `DJANGO_DEBUG=false`

Vercel now detects Django projects directly from `manage.py` and the WSGI
entrypoint, so the included `vercel.json` deliberately avoids legacy build and
route overrides. Apply database migrations from a controlled release
environment rather than from every serverless build.
