source .env
source "$JIRABOT_VENV_PATH/bin/activate"
gunicorn --bind 0.0.0.0:3000 wsgi:app
