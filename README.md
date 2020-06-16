# jirabot v0.6
Tiny Slack app that hyperlinks Service Desk tickets.

## Latest updates
* v0.6: added Windows support

## Details
This app is in development for a personal project and should not be used in production.

If you *must* implement this yourself, you'll need the following:

* a MySQL database called `jirabot` with the following tables:
```
Table `teams`:
+--------------+---------------+------+-----+---------+-------+
| Field        | Type          | Null | Key | Default | Extra |
+--------------+---------------+------+-----+---------+-------+
| team_no      | varchar(64)   | NO   | PRI | NULL    |       |
| url          | varchar(2048) | YES  |     | NULL    |       |
| error_sent   | tinyint(1)    | NO   |     | 0       |       |
| access_token | varchar(128)  | NO   |     | NULL    |       |
+--------------+---------------+------+-----+---------+-------+
```
```
Table `messages`:
+------------+--------------+------+-----+---------+-------+
| Field      | Type         | Null | Key | Default | Extra |
+------------+--------------+------+-----+---------+-------+
| team_no    | varchar(64)  | NO   | PRI | NULL    |       |
| channel_id | varchar(64)  | NO   | PRI | NULL    |       |
| msg_id     | varchar(128) | NO   | PRI | NULL    |       |
| payload    | mediumtext   | NO   |     | NULL    |       |
| tickets    | mediumtext   | NO   |     | NULL    |       |
+------------+--------------+------+-----+---------+-------+
```
* the packages listed in [requirements.txt](requirements.txt) installed in your Python environment (note the choice between WSGI server packages `waitress` or `gunicorn` for Windows or Unix, respectively)
* Python 3.6+

**On Windows:**
* a file `env.ps1` in the project directory with the following variables, replacing the values with the relevant details of your Slack app registration:
```posh
$Env:JIRABOT_VENV_PATH = "\path\to\venv";
$Env:SLACK_VERIFICATION_TOKEN = "ABCxyz123";
$Env:SLACK_SIGNING_SECRET = "123abc";
$Env:SLACK_CLIENT_SECRET = "123abc";
$Env:SLACK_CLIENT_ID = "12345.67890";
```

To run the app on Windows, run `.\run.ps1` and expose port 3000 with your choice of methods. I recommend [ngrok](https://ngrok.com/) for testing purposes.

**On Unix:**
* a file `.env` in the project directory with the following variables, replacing the values with the relevant details of your Slack app registration:
```sh
export JIRABOT_VENV_PATH='/path/to/venv'
export SLACK_VERIFICATION_TOKEN=ABCxyz123
export SLACK_SIGNING_SECRET=123abc
export SLACK_CLIENT_SECRET=123abc
export SLACK_CLIENT_ID='12345.67890'
```

To run the app on Unix, run `./run.sh` and expose port 3000 with your choice of methods. I recommend [ngrok](https://ngrok.com/) for testing purposes.
