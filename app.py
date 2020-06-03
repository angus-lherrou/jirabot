import os
import json
import logging
import re
from flask import abort, Flask, request, redirect
import requests
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from jirabot_link import JirabotLink
import ssl as ssl_lib
import certifi

ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

# Initialize a Flask app to host the events adapter
app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)

ticket_links_sent = {}

if not os.path.exists('creds.json'):
    creds = {os.environ['SLACK_TEAM_ID']: {'access_token': os.environ['SLACK_BOT_TOKEN'], 'error_sent': False, 'url': ''}}
else:
    with open('creds.json', 'r') as creds_json_init:
        creds = json.load(creds_json_init)

clients = {}

PATTERN = r"[A-Z]+-\d+"


def is_request_valid(rqst):
    is_token_valid = rqst.form['token'] == os.environ['SLACK_VERIFICATION_TOKEN']
    is_team_valid = rqst.form['team_id'] in creds
    return is_token_valid and is_team_valid


@app.route('/slack/sd-url', methods=['POST'])
def setup_sd_url():
    if not is_request_valid(request):
        abort(400)
    else:
        url = request.form['text']
        creds[request.form['team_id']]['url'] = url
        with open('creds.json', 'w') as creds_json:
            json.dump(creds, creds_json)
        return f"Successfully updated Service Desk URL to {url}."


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
    print(resp)
    if 'team' in resp:
        team_id = resp['team']['id']
        creds[team_id] = resp
        creds[team_id]['url'] = ''
        creds[team_id]['error_sent'] = False
    with open('creds.json', 'w') as creds_json:
        json.dump(creds, creds_json)
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
    assert team_id in creds
    url = creds[team_id]['url']
    error_sent = creds[team_id]['error_sent']
    link_maker = JirabotLink(channel, url, tickets)

    # Get the message payload
    if not url:
        msg = link_maker.get_message_payload(error=True)
    else:
        msg = link_maker.get_message_payload()

    if url or not error_sent:
        # Post the message in Slack
        response = webclient.chat_postMessage(**msg)

        # Capture the timestamp of the message we've just posted so
        # we can use it to update the message (?)
        link_maker.timestamp = response["ts"]

        # Store the message sent in ticket_links_sent
        if channel not in ticket_links_sent:
            ticket_links_sent[channel] = {}
        ticket_links_sent[channel][msg_id] = link_maker

    if not url:
        creds[team_id]['error_sent'] = True
        with open('creds.json', 'w') as creds_json:
            json.dump(creds, creds_json)


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
            if channel_id not in ticket_links_sent:
                return
            else:
                # Get the original link maker sent.
                if msg_id in ticket_links_sent[channel_id]:
                    link_maker = ticket_links_sent[channel_id][msg_id]

                    if len(new_tickets) > 0:
                        # Update the list of tickets
                        link_maker.tickets = new_tickets

                        # Get the new message payload
                        msg = link_maker.get_message_payload()

                        # Post the updated message in Slack
                        updated_message = webclient.chat_update(**msg)

                        # Update the timestamp saved on the onboarding tutorial object
                        link_maker.timestamp = updated_message["ts"]
                    else:
                        msg = link_maker.get_message_payload()
                        webclient.chat_delete(**msg)
                        ticket_links_sent[channel_id].pop(msg_id)
                else:
                    if len(new_tickets) > 0:
                        make_links(webclient, team_id, msg_id, channel_id, new_tickets)
    elif subtype == 'message_deleted':
        if channel_id not in ticket_links_sent:
            return
        prev_msg_dict = event.get('previous_message')
        if prev_msg_dict.get('bot_id'):
            return
        msg_id = prev_msg_dict.get('client_msg_id')
        link_maker = ticket_links_sent[channel_id][msg_id]
        msg = link_maker.get_message_payload()
        webclient.chat_delete(**msg)
        ticket_links_sent[channel_id].pop(msg_id)
    elif text:
        tickets = detect_all_ticket_mentions(text)
        if len(tickets) > 0:
            make_links(webclient, team_id, msg_id, channel_id, tickets)


def get_or_create_webclient(team_id) -> WebClient:
    if team_id not in clients:
        clients[team_id] = WebClient(token=creds[team_id]['access_token'])
    return clients[team_id]


def detect_all_ticket_mentions(message_text):
    return re.findall(PATTERN, message_text)


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    app.run(port=3000)
