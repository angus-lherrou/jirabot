"""
jirabot v0.6
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot

WSGI runner for use with waitress on Windows.
"""
from app import app
from waitress import serve


if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=3000)
