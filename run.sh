source ./.env
source ../venv/bin/activate
gunicorn --bind 0.0.0.0:3000 wsgi:app
