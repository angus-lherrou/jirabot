"""
jirabot v0.4
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot
"""
import os
import json
import re
import ssl as ssl_lib
from flask import abort, Flask, request, redirect
import requests
from slack import WebClient
from slackeventsapi import SlackEventAdapter
import certifi
from jirabot_link import JirabotLink
from sql_queries import QUERIES, establish_cnx

# Create ssl context
ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

"""MySQL database connection"""
CNX = establish_cnx()

"""MySQL cursor"""
CURSOR = CNX.cursor()

# Initialize a Flask app to host the events adapter
app = Flask(__name__)

# Set up the Slack Events Adaptor
EVENT_ADAPTER = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)

"""Dictionary of this session's Slack WebClient objects"""
CLIENTS = {}

"""Regex pattern for finding ticket IDs"""
PATTERN = r"[A-Z]+-\d+"


def is_request_valid() -> bool:
    """
    Checks whether a /sd-url request is valid.
    :return: whether the request's token matches the known
             verification token and whether the team ID is
             present in the database.
    """
    is_token_valid = request.form['token'] == os.environ['SLACK_VERIFICATION_TOKEN']
    CURSOR.execute(QUERIES.team_exists, (request.form['team_id'],))
    is_team_valid = bool(CURSOR.fetchone())
    return is_token_valid and is_team_valid


@app.route('/slack/sd-url', methods=['POST'])
def setup_sd_url():
    """
    Processes the slash command /sd-url.
    :return: the message to post to Slack describing the result of the command
    """
    if not is_request_valid():
        abort(400)
    else:
        url = request.form['text']
        team_id = request.form['team_id']
        CURSOR.execute(QUERIES.update_url, (url, team_id))
        CNX.commit()
        CURSOR.execute(QUERIES.select_url_and_error, (team_id,))
        result = CURSOR.fetchone()
        if result:
            new_url, _ = result
        else:
            return f"Failed to update url to {url}: team does not exist."
        if new_url == url:
            return f"Successfully updated Service Desk URL to {url}."
        return (f"Failed to update url to {url}: database did not accept update.\n"
                f"Current url: {new_url}")


@app.route('/slack/oauth', methods=['GET'])
def do_auth():
    """
    OAuth redirect function. Fetches and stores an access token for a new team.
    :return: an HTTP 302 redirect
    """
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
        CURSOR.execute(QUERIES.insert_new_team, (team_id, resp['access_token']))
        CNX.commit()
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


def make_links(webclient: WebClient, team_id: str, msg_id: str, channel: str, tickets) -> None:
    """
    Posts a new message to Slack.
    :param webclient: the Slack WebClient to post to
    :param team_id: the Slack team ID
    :param msg_id: the message ID for storing the message details in the database
    :param channel: the Slack channel to post to
    :param tickets: the list of ticket IDs to link to
    :return: None
    """

    # Check that team_id exists in database
    CURSOR.execute(QUERIES.team_exists, (team_id,))
    assert CURSOR.fetchone()

    # Fetch the URL (or None) and no-url error status
    CURSOR.execute(QUERIES.select_url_and_error, (team_id,))
    url, error_sent = fetch_or_error(CURSOR.fetchone(), 'team not set up correctly in database')

    # Create the link maker
    link_maker = JirabotLink.from_kwargs(channel=channel, url=url, tickets=tickets, timestamp='')

    # Get the message payload
    if not url:
        # Get error message
        msg, _, _ = link_maker.get_message_payload(error=("Error: Service Desk URL not set up yet."
                                                          "\nUse `/sd-url <url>` first."))
        # Record no-url error as sent
        CURSOR.execute(QUERIES.update_error, (True, team_id))
        CNX.commit()
    else:
        # Get links message
        msg, _, _ = link_maker.get_message_payload()

    if url or not error_sent:
        # Post the message in Slack
        response = webclient.chat_postMessage(**msg)

        # Capture the timestamp of the message we've just posted so
        # we can use it to update the message (?)

        msg.update(ts=response["ts"])

        # Store the message sent in the database
        CURSOR.execute(QUERIES.insert_new_message,
                       (team_id, channel, msg_id, json.dumps(msg), json.dumps(tickets)))
        CNX.commit()


@EVENT_ADAPTER.on("message")
def message(payload) -> None:
    """Display the onboarding welcome message after receiving a message
    that contains "start".
    :param payload: the contents of the message event
    :return: None
    """

    # Retrieve event data from the incoming message payload
    event = payload.get("event", {})
    channel_id = event.get("channel")
    subtype = event.get("subtype")
    msg_id = event.get('client_msg_id')
    text = event.get("text")
    team_id = payload.get("team_id")

    # Get or create the Slack WebClient for this team
    web_client = get_or_create_webclient(team_id)

    # End early if the message is a bot message
    if event.get('bot_id'):
        return

    # Condition: edited message
    if subtype == 'message_changed':
        # End early if the message is a bot message
        message_dict = event.get('message')
        if message_dict.get('bot_id'):
            return

        # Get message ID (stored differently for messaged_changed events)
        msg_id = message_dict.get('client_msg_id')

        # Get lists of tickets mentioned in previous message version and new message version
        old_tickets = detect_all_ticket_mentions(event.get('previous_message').get('text'))
        new_tickets = detect_all_ticket_mentions(message_dict.get('text'))

        # We only care if the ticket mentions have changed
        if set(old_tickets) != set(new_tickets):
            # Check whether links were sent for this message earlier
            CURSOR.execute(QUERIES.select_messages, (team_id, channel_id))
            if (msg_id,) in CURSOR.fetchall():
                # Get the original bot message data
                CURSOR.execute(QUERIES.select_payload_url_and_tickets,
                               (team_id, channel_id, msg_id))

                msg, url, tickets = fetch_or_error(CURSOR.fetchone(),
                                                   'no message found, serious problem')

                # Create a link maker
                link_maker = JirabotLink.from_json(json.loads(msg), url, json.loads(tickets))

                # If there are tickets mentioned in the new result, edit the bot response
                if len(new_tickets) > 0:
                    # Update the list of tickets
                    link_maker.tickets = new_tickets

                    # Get the new message payload
                    msg, _, _ = link_maker.get_message_payload()

                    # Post the updated message in Slack
                    updated_message = web_client.chat_update(**msg)

                    # Update the timestamp
                    msg.update(ts=updated_message["ts"])

                    # Update the bot message payload data in the database
                    CURSOR.execute(QUERIES.update_message_payload,
                                   (json.dumps(msg), json.dumps(new_tickets),
                                    team_id, channel_id, msg_id))
                    CNX.commit()
                # If there are no tickets mentioned in the new result, delete the bot response
                else:
                    msg, _, _ = link_maker.get_message_payload()
                    delete_message(web_client, msg, team_id, channel_id, msg_id)
            # If no links were sent for this message previously, send them now
            elif len(new_tickets) > 0:
                make_links(web_client, team_id, msg_id, channel_id, new_tickets)

    # Condition: deleted message
    elif subtype == 'message_deleted':
        # End early if the message is a bot message
        prev_msg_dict = event.get('previous_message')
        if prev_msg_dict.get('bot_id'):
            return

        # Get message ID (stored differently for message_deleted events)
        msg_id = prev_msg_dict.get('client_msg_id')

        # Fetch bot message data related to the message being deleted, if it exists
        CURSOR.execute(QUERIES.select_payload_url_and_tickets, (team_id, channel_id, msg_id))
        result = CURSOR.fetchone()

        # If a result exists, there is a bot response to delete, so delete it
        if result:
            msg, _, _ = result
            delete_message(web_client, msg, team_id, channel_id, msg_id)

    # Condition: new message with text contents
    elif text:
        # Get list of tickets mentioned in the message
        tickets = detect_all_ticket_mentions(text)

        # If there are any tickets mentioned, post a bot response
        if len(tickets) > 0:
            make_links(web_client, team_id, msg_id, channel_id, tickets)


def delete_message(web_client, msg, team_id, channel_id, msg_id) -> None:
    """
    Deletes a bot response from Slack.
    :param web_client: the WebClient to use
    :param msg: the bot response payload
    :param team_id: the team ID
    :param channel_id: the channel ID
    :param msg_id: the message ID of the related message
    :return: None
    """
    web_client.chat_delete(**msg)
    CURSOR.execute(QUERIES.delete_message, (team_id, channel_id, msg_id))
    CNX.commit()


def fetch_or_error(result: tuple, error: str) -> tuple:
    """
    Error raiser for unpacking issues resulting from empty select queries
    :param result: the result to unpack
    :param error: the error message to raise if the result is empty
    :return: the result, to be unpacked
    """
    if result:
        return result
    raise KeyError(error)


def get_or_create_webclient(team_id) -> WebClient:
    """
    Creates a new Slack WebClient for a specific team, or fetches the existing
    WebClient for the team if it has already been created this session.
    :param team_id: the Slack team ID
    :return: the WebClient for the given team
    """
    if team_id not in CLIENTS:
        CURSOR.execute(QUERIES.select_access_token, (team_id,))
        result = CURSOR.fetchone()
        if result:
            (access_token,) = result
        else:
            raise KeyError('Team ID not in database')
        assert not CURSOR.fetchone()
        CLIENTS[team_id] = WebClient(token=access_token)
    return CLIENTS[team_id]


def detect_all_ticket_mentions(message_text):
    """
    Regex to grab the ticket numbers to link to.
    :param message_text: the message body
    :return: a list of matching strings
    """
    return re.findall(PATTERN, message_text)
