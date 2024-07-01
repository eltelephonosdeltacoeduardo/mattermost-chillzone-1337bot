"""Typing event class for the scorebot."""

"""
sample event_data:
{
    "event": "typing",
    "data": {"parent_id": "", "user_id": "fx11aeu3pjrwid66u4xoiece8h"},
    "broadcast": {
        "omit_users": {"fx11aeu3pjrwid66u4xoiece8h": True},
        "user_id": "",
        "channel_id": "3dwt4m4qst8pzr4p3843t8a6hc",
        "team_id": "",
        "connection_id": "",
        "omit_connection_id": "",
    },
    "seq": 2,
}
"""
from datetime import datetime


class TypingEvent:
    def __init__(self, event, scorebot):
        self.event = event
        self.data = event["data"]
        self.broadcast = event["broadcast"]
        self.time = datetime.now()
        self.seq = event["seq"]
        self.parent_id = self.data["parent_id"]
        self.user_id = self.data["user_id"]
        self.username = scorebot.get_user(self.user_id)["username"]
        self.username_no_hl = self.username[:1] + "\u200B" + self.username[1:]
        self.channel_id = self.broadcast["channel_id"]
        self.channel = scorebot.get_channel(self.channel_id)
        self.channel_name = self.channel["name"]

        self.team_id = self.broadcast["team_id"]
        self.omit_users = self.broadcast["omit_users"]
        self.omit_connection_id = self.broadcast["omit_connection_id"]
        self.is_in_channel = self.channel_id in scorebot.config["MATTERMOST_CHANNELS"]
