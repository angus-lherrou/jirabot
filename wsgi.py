"""
jirabot v0.6
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot

WSGI runner for use with gunicorn on Unix.
"""
from app import app


if __name__ == "__main__":
    app.run()
