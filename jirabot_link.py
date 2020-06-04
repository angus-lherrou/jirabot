"""
jirabot v0.5
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot

JirabotLink object for generating bot response payloads.
"""


class JirabotLink:
    """Constructs the ticket link message"""

    def __init__(self, **kwargs):
        self.channel = kwargs['channel']
        self.url = kwargs['url']
        self.tickets = kwargs['tickets']
        self.timestamp = kwargs['timestamp']

    @classmethod
    def from_kwargs(cls, **kwargs):
        return cls(**kwargs)

    @classmethod
    def from_json(cls, json: dict, url: str, tickets: list):
        return cls(timestamp=json['ts'],
                   channel=json['channel'],
                   url=url,
                   tickets=tickets)

    def get_message_payload(self, error: str = ''):
        return {
            "ts": self.timestamp,
            "channel": self.channel,
            "blocks": (
                [
                    *self._get_link_block(),
                ] if not error else self._format_error(error)
            ),
        }, self.url, self.tickets

    @staticmethod
    def _format_error(msg: str) -> list:
        return [
            {
                "type": "section",
                "text":
                    {
                        "type": "mrkdwn",
                        "text": msg
                    }
            },
        ]

    def _get_link_block(self):
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Links to tickets mentioned:"}},
            {
                "type": "context",
                "elements":
                    [
                        {
                            "type": "mrkdwn",
                            "text": f"<{self._get_jira_link(self.url, ticket)}|{ticket}>"
                        }
                        for ticket in self.tickets
                    ]
            }
        ]

    @staticmethod
    def _get_jira_link(url, ticket):
        return f"{url}/{ticket}"
