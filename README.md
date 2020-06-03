# jirabot v0.1
Tiny Slack app that hyperlinks Service Desk tickets.

## Details
This app is in development for a personal project and should not be used in production.

If you *must* implement this yourself, you'll need a file `.env` in the project directory with the following variables:
```sh
export SLACK_TEAM_ID=T123ABC
export SLACK_VERIFICATION_TOKEN=ABCxyz123
export SLACK_BOT_TOKEN=abcd-123456-456789-ABCxyz789
export SLACK_SIGNING_SECRET=123abc
export SLACK_CLIENT_SECRET=123abc
export SLACK_CLIENT_ID='12345.67890'
```
Replace the values for these environment variables with the relevant details of your Slack app registration.
