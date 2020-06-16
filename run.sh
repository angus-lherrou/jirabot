# jirabot v0.6
# Angus L'Herrou
# piraka@brandeis.edu
# github.com/angus-lherrou/jirabot
# Unix shell run script

source .env
source "$JIRABOT_VENV_PATH/bin/activate"
gunicorn --bind 0.0.0.0:3000 wsgi:app
