"""
jirabot v0.5
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot

WSGI runner for use with gunicorn.
"""


from app import app

if __name__ == "__main__":
    app.run()
