"""
jirabot v0.2
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot
"""
import os
import json
import re
import getpass
import mysql.connector
from flask import abort, Flask, request, redirect
import requests
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from jirabot_link import JirabotLink
import ssl as ssl_lib
import certifi

"""
Table `teams`:
+--------------+---------------+------+-----+---------+-------+
| Field        | Type          | Null | Key | Default | Extra |
+--------------+---------------+------+-----+---------+-------+
| team_no      | varchar(64)   | NO   | PRI | NULL    |       |
| url          | varchar(2048) | YES  |     | NULL    |       |
| error_sent   | tinyint(1)    | NO   |     | 0       |       |
| access_token | varchar(128)  | NO   |     | NULL    |       |
+--------------+---------------+------+-----+---------+-------+

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
"""

cnx = mysql.connector.connect(user='root', database='jirabot',
                              password=getpass.getpass(prompt="Password > "))
cursor = cnx.cursor()

insert_new_team = ("INSERT INTO teams "
                   "(team_no, access_token) "
                   "VALUES (%s, %s)")
update_url = ("UPDATE teams "
              "SET url = %s "
              "WHERE team_no = %s")
update_error = ("UPDATE teams "
                "SET error_sent = %d "
                "WHERE team_no = %s")
team_exists = ("SELECT team_no "
               "FROM teams "
               "WHERE team_no = %s")
select_url_and_error = ("SELECT url, error_sent "
                        "FROM teams "
                        "WHERE team_no = %s")
select_access_token = ("SELECT access_token "
                       "FROM teams "
                       "WHERE team_no = %s")
insert_new_message = ("INSERT INTO messages "
                      "(team_no, channel_id, msg_id, payload, tickets) "
                      "VALUES (%s, %s, %s, %s, %s)")
update_message_payload = ("UPDATE messages "
                          "SET payload = %s, tickets = %s "
                          "WHERE (team_no, channel_id, msg_id) = (%s, %s, %s)")
delete_message = ("DELETE FROM messages "
                  "WHERE (team_no, channel_id, msg_id) = (%s, %s, %s)")
select_channels = ("SELECT channel_id "
                   "FROM messages "
                   "WHERE team_no = %s")
select_messages = ("SELECT msg_id "
                   "FROM messages "
                   "WHERE (team_no, channel_id) = (%s, %s)")
select_payload_url_and_tickets = ("SELECT payload, url, tickets "
                                  "FROM messages AS M, teams AS T "
                                  "WHERE T.team_no = M.team_no "
                                  "AND (M.team_no, M.channel_id, M.msg_id) = (%s, %s, %s)")

ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

# Initialize a Flask app to host the events adapter
app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)

clients = {}

PATTERN = r"[A-Z]+-\d+"


def is_request_valid(rqst):
    is_token_valid = rqst.form['token'] == os.environ['SLACK_VERIFICATION_TOKEN']
    cursor.execute(team_exists, (rqst.form['team_id'],))
    is_team_valid = bool(cursor.fetchone())
    return is_token_valid and is_team_valid


@app.route('/slack/sd-url', methods=['POST'])
def setup_sd_url():
    if not is_request_valid(request):
        abort(400)
    else:
        url = request.form['text']
        team_id = request.form['team_id']
        cursor.execute(update_url, (url, team_id))
        cnx.commit()
        cursor.execute(select_url_and_error, (team_id,))
        result = cursor.fetchone()
        if result:
            new_url, error = result
        else:
            return f"Failed to update url to {url}: team does not exist."
        if new_url == url:
            return f"Successfully updated Service Desk URL to {url}."
        else:
            return (f"Failed to update url to {url}: database did not accept update.\n"
                    f"Current url: {new_url}")


@app.route('/slack/oauth', methods=['GET'])
def do_auth():
    url = "https://slack.com/api/oauth.v2.access"
    client_id = os.environ['SLACK_CLIENT_ID']
    client_secret = os.environ['SLACK_CLIENT_SECRET']
    data = {
        'code': request.args.get('code'),
    }
    auth = (client_id.encode('utf-8'), client_secret.encode('utf-8'))
    resp = requests.post(url, data=data, auth=auth).json()
    if 'team' in resp:
        team_id = resp['team']['id']
        cursor.execute(insert_new_team, (team_id, resp['access_token']))
        cnx.commit()
    scope = [
        'channels:history',
        'groups:history',
        'mpim:history',
        'mpim:write',
        'im:history',
        'im:write',
        'commands',
        'chat:write'
    ]
    return redirect(f'https://slack.com/oauth/v2/authorize?client_id={client_id}'
                    f'&scope={",".join(scope)}', 302)


def make_links(webclient: WebClient, team_id: str, msg_id: str, channel: str, tickets):
    # Create a new link maker object
    cursor.execute(team_exists, (team_id,))
    assert cursor.fetchone()
    cursor.execute(select_url_and_error, (team_id,))
    result = cursor.fetchone()
    if result:
        url, error_sent = result
    else:
        msg = {
            "ts": "",
            "channel": channel,
            "blocks": (
                [
                    {
                        "type": "section",
                        "text":
                            {
                                "type": "mrkdwn",
                                "text":
                                    (
                                        "Error: team not set up. Contact your database admin."
                                    )
                            }
                    },
                ]
            ),
        }
        webclient.chat_postMessage(**msg)
        return

    assert not cursor.fetchone()
    link_maker = JirabotLink.from_kwargs(channel=channel, url=url, tickets=tickets, timestamp='')

    # Get the message payload
    if not url:
        msg, _, _ = link_maker.get_message_payload(error=True)
    else:
        msg, _, _ = link_maker.get_message_payload()

    if url or not error_sent:
        # Post the message in Slack
        response = webclient.chat_postMessage(**msg)

        # Capture the timestamp of the message we've just posted so
        # we can use it to update the message (?)
        link_maker.timestamp = response["ts"]

        msg, _, _ = link_maker.get_message_payload()

        # Store the message sent in the database
        cursor.execute(insert_new_message,
                       (team_id, channel, msg_id, json.dumps(msg), json.dumps(tickets)))
        cnx.commit()
    if not url:
        cursor.execute(update_error, (True, team_id))
        cnx.commit()


# ============== Message Events ============= #
# When a user sends a message, the event type will be 'message'.
# Here we'll link the message callback to the 'message' event.
@slack_events_adapter.on("message")
def message(payload):
    """Display the onboarding welcome message after receiving a message
    that contains "start".
    """
    event = payload.get("event", {})

    channel_id = event.get("channel")
    subtype = event.get("subtype")
    msg_id = event.get('client_msg_id')
    text = event.get("text")
    team_id = payload.get("team_id")
    webclient = get_or_create_webclient(team_id)
    if event.get('bot_id'):
        return

    if subtype == 'message_changed':
        message_dict = event.get('message')
        if message_dict.get('bot_id'):
            return
        old_tickets = detect_all_ticket_mentions(event.get('previous_message').get('text'))
        new_tickets = detect_all_ticket_mentions(message_dict.get('text'))
        msg_id = message_dict.get('client_msg_id')
        if set(old_tickets) != set(new_tickets):
            cursor.execute(select_channels, (team_id,))
            if (channel_id,) not in cursor.fetchall():
                return
            else:
                # Get the original link maker sent.
                cursor.execute(select_messages, (team_id, channel_id))
                if (msg_id,) in cursor.fetchall():
                    cursor.execute(select_payload_url_and_tickets, (team_id, channel_id, msg_id))
                    result = cursor.fetchone()
                    assert not cursor.fetchone()
                    if result:
                        payload, url, tickets = result
                    else:
                        raise KeyError('no message found, serious problem')
                    link_maker = JirabotLink.from_json(json.loads(payload),
                                                       url,
                                                       json.loads(tickets))

                    if len(new_tickets) > 0:
                        # Update the list of tickets
                        link_maker.tickets = new_tickets

                        # Get the new message payload
                        msg, _, _ = link_maker.get_message_payload()

                        # Post the updated message in Slack
                        updated_message = webclient.chat_update(**msg)

                        # Update the timestamp
                        msg.update(ts=updated_message["ts"])

                        cursor.execute(update_message_payload,
                                       (json.dumps(msg), json.dumps(new_tickets),
                                        team_id, channel_id, msg_id))
                        cnx.commit()
                    else:
                        msg, _, _ = link_maker.get_message_payload()
                        webclient.chat_delete(**msg)
                        cursor.execute(delete_message, (team_id, channel_id, msg_id))
                        cnx.commit()
                else:
                    if len(new_tickets) > 0:
                        make_links(webclient, team_id, msg_id, channel_id, new_tickets)
    elif subtype == 'message_deleted':
        cursor.execute(select_channels, (team_id,))
        if (channel_id,) not in cursor.fetchall():
            return
        prev_msg_dict = event.get('previous_message')
        if prev_msg_dict.get('bot_id'):
            return
        msg_id = prev_msg_dict.get('client_msg_id')
        cursor.execute(select_payload_url_and_tickets, (team_id, channel_id, msg_id))
        result = cursor.fetchone()
        assert not cursor.fetchone()
        if result:
            payload, url, tickets = result
        else:
            raise KeyError('no message found, serious problem')
        webclient.chat_delete(**json.loads(payload))
    elif text:
        tickets = detect_all_ticket_mentions(text)
        if len(tickets) > 0:
            make_links(webclient, team_id, msg_id, channel_id, tickets)


def get_or_create_webclient(team_id) -> WebClient:
    if team_id not in clients:
        cursor.execute(select_access_token, (team_id,))
        result = cursor.fetchone()
        if result:
            (access_token,) = result
        else:
            raise KeyError('Team ID not in database')
        assert not cursor.fetchone()
        clients[team_id] = WebClient(token=access_token)
    return clients[team_id]


def detect_all_ticket_mentions(message_text):
    return re.findall(PATTERN, message_text)
