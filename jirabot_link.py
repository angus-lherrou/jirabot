NO_URL_ERROR = [
            {
                "type": "section",
                "text":
                    {
                        "type": "mrkdwn",
                        "text":
                            (
                                "Error: Service Desk URL not set up yet.\n"
                                "Use `/sd-url <url>` first."
                            )
                    }
            },
        ]


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

    def get_message_payload(self, error=False):
        return {
            "ts": self.timestamp,
            "channel": self.channel,
            "blocks": (
                [
                    *self._get_link_block(),
                ] if not error else NO_URL_ERROR
            ),
        }, self.url, self.tickets

    @staticmethod
    def amend_message_payload(payload: dict, **kwargs):
        return payload.update(kwargs)

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
