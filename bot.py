#!/bin/python3

###########################
# 1337 bot for Mattermost
###########################

# TODO: Use local time only?

import json
import asyncio
import os
import sys
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import redis
import pytz
from dotenv import load_dotenv
from mattermostdriver import Driver
import logging
import ssl_fix
import random
from typingevent import TypingEvent

load_dotenv()

class ScoreBot:
    def __init__(self):
        # Config
        # get a list of channels from the environment variable, or use a default list
        channels_default = ["1337", "1337dev", "1337evenmoredev"]
        channels = os.getenv("MATTERMOST_CHANNELS")
        if channels:
            # comma seperated list of channels
            channels = channels.split(",")
            # trim whitespace from the channel names
            channels = [channel.strip() for channel in channels]
        else:
            channels = channels_default
        self.config = {
            "REDIS_HOST": os.getenv("REDIS_HOST"),
            "REDIS_PORT": int(os.getenv("REDIS_PORT")),
            "REDIS_DB": int(os.getenv("REDIS_DB", "0")),
            "MATTERMOST_URL": os.getenv("MATTERMOST_URL"),
            "MATTERMOST_TOKEN": os.getenv("MATTERMOST_TOKEN"),
            "MATTERMOST_SCHEME": os.getenv("MATTERMOST_SCHEME"),
            "MATTERMOST_PORT": int(os.getenv("MATTERMOST_PORT")),
            "MATTERMOST_CHANNELS": channels,
            "DEBUG": int(os.getenv("DEBUG", "0")),
            "DEBUG_EARLY": int(os.getenv("DEBUG_EARLY", "0")),
            "DEBUG_TYPING": int(os.getenv("DEBUG_TYPING", "0")),
            "DRIVERDEBUG": int(os.getenv("DRIVERDEBUG", "0")),
            "POINTS": [
                {"points": 15, "emoji": "first_place_medal"},
                {"points": 10, "emoji": "second_place_medal"},
                {"points": 5, "emoji": "third_place_medal"},
                # Fallback entry for too slow responses (0 points and a specific emoji)
                {"points": 0, "emoji": "turtle"},
            ],
            "FEATURE_IS_TYPING": os.getenv("FEATURE_IS_TYPING", "0").lower()
            in ["true", "1"],
            "FEATURE_IS_EARLY": os.getenv("FEATURE_IS_EARLY", "0").lower()
            in ["true", "1"],

        }
        self.debug_early = self.config["DEBUG_EARLY"] if self.config["DEBUG_EARLY"] else False
        self.debug_typing = self.config["DEBUG_TYPING"] if self.config["DEBUG_TYPING"] else False
        self.debug = self.config["DEBUG"] if self.config["DEBUG"] else False
        self.driverdebug = (
            self.config["DRIVERDEBUG"] if self.config["DRIVERDEBUG"] else False
        )
        

        log_format: str = "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
        log_date_format: str = "%Y-%m-%d %H:%M:%S"
        logging.basicConfig(
            **{
                "stream": sys.stdout,
                "format": log_format,
                "datefmt": log_date_format,
                "level": logging.DEBUG if self.debug else logging.INFO,
            }
        )
        self.logger = logging.getLogger("ScoreBot")

        # Redis
        self.redis_client = redis.StrictRedis(
            host=self.config['REDIS_HOST'],
            port=self.config['REDIS_PORT'],
            decode_responses=True,
            db=self.config["REDIS_DB"]
        )

        # Mattermost
        self.mattermost = Driver(
            {
                "url": self.config["MATTERMOST_URL"],
                "token": self.config["MATTERMOST_TOKEN"],
                "scheme": self.config["MATTERMOST_SCHEME"],
                "port": self.config["MATTERMOST_PORT"],
                "debug": self.driverdebug,
            }
        )
        self.logger.debug("Mattermost driver initialized")
        self.logger.info("ScoreBot initialized")

    def run(self):
        self.mattermost.login()
        self.mattermost.init_websocket(self.event_handler)

    async def event_handler(self, event):
        try:
            message = json.loads(event)

            # Output the message to the console along with the date and time
            self.logger.debug(message)

            if 'data' in message and 'post' in message['data']:
                post = json.loads(message['data']['post'])
                # only handle new posts in the channels we are interested in
                self.logger.debug(f"Checking if we should handle the message")
                self.logger.debug(f"channels: {self.config['MATTERMOST_CHANNELS']}")
                if post['create_at'] == post['update_at'] and message['data']['channel_name'] in self.config['MATTERMOST_CHANNELS']:
                    # Pick out the relevant data from the post
                    parsed = {}
                    parsed['create_at']     = post['create_at']
                    parsed['update_at']     = post['update_at']
                    parsed['channel_id']    = post['channel_id']
                    parsed['post_id']       = post['id']
                    parsed['message']       = post['message']
                    parsed['user_id']       = post['user_id']
                    parsed['username']      = message['data']['sender_name'][1:] if message['data']['sender_name'].startswith("@") else message['data']['sender_name']
                    parsed['channel_name']  = message['data']['channel_name']

                    self.handle_message(parsed)
            elif "event" in message and message["event"] == "typing":
                if self.config["FEATURE_IS_TYPING"]:
                    typing_event = TypingEvent(message, self)
                    self.handle_typing_event(typing_event)

        except Exception as e:
            print(f"Error in event_handler: {e}")

    def handle_typing_event(self, event):
        """Handle typing events"""
        self.logger.debug(
            f"User {event.username} is typing in channel {event.channel_name} at {event.time}"
        )
        random_entering_quotes = [
            "<user> has entered the game...",
            "<user> is getting ready to play 1337!",
            "The game is on <user>!",
            "<user> remember the only rule about 1337, you do not talk about 1337!",
            "if <user> is typing, it must be 1337 time!",
            "I'm sorry <user>, I'm afraid I can't do that. It's 1337 time!",
            "If you build it, <user> will come. It's 1337 time!",
            "It's the final countdown <user>!",
            "I feel a disturbance in the force <user>. It's 1337 time!",
            "Look who is finally here <user>!",
            "Look who bothered to show up today, <user>!",
            "If <user> is looking fly, you must comply. It's 1337 time!",
            "I'm sorry <user> i am running out of clever things to say. It's 1337 time!",
        ]
        # if channel not in the list of channels, return
        if event.channel_name not in self.config["MATTERMOST_CHANNELS"]:
            return

        # if time is 1336, send a random quote to the channel"
        if self.debug_early or event.time.strftime("%H%M") == "1336":
            # get the key for the previous day and the current day
            yesterdays_key = (event.time - timedelta(days=1)).strftime(
                "%Y%m%d"
            ) + event.channel_id
            today_key = event.time.strftime("%Y%m%d") + event.channel_id

            # cleanup the previous day's set
            if self.redis_client.exists(yesterdays_key):
                self.redis_client.delete(yesterdays_key)

            # if the user is not in the set, add the user to the set and send a random quote
            if not self.redis_client.sismember(today_key, event.username):
                self.redis_client.sadd(today_key, event.username)
                # replace <user> with the username
                random_quote = random.choice(random_entering_quotes).replace(
                    "<user>", f"@{event.username_no_hl}"
                )
                self.send_message(event.channel_id, random_quote)

    def get_mental_lag_for_user_id(
        self, channel_id, yearmonth, user_id
    ) -> tuple[int, int]:
        key = f"speed:{channel_id}:{yearmonth}:*:{user_id}"
        keys = self.redis_client.keys(key)
        self.logger.debug(f"keys: {keys}")
        if keys:
            total = 0
            for k in keys:
                total += int(self.redis_client.get(k))
            average = int(total / len(keys))
            min = 60000
            for k in keys:
                k_ms = int(self.redis_client.get(k))
                if k_ms < min:
                    min = k_ms
            fastest = min
            return (fastest, average)
        else:
            return (0, 0)

    def handle_early(self, post, post_time):
        """Handle the case where the user is early."""
        cph_tz = pytz.timezone('Europe/Copenhagen')
        if self.debug_early:
            # if debug use the time from the post instead of the current time to ensure the correct time is used
            today_1336_cph = post_time.replace(second=0, microsecond=0)
        else:
            today_1336_cph = datetime.now(cph_tz).replace(
                hour=13, minute=37, second=0, microsecond=0
            )
        timestamp_dt = datetime.fromtimestamp(post['create_at'] / 1000, cph_tz)
        difference_s = round((timestamp_dt - today_1336_cph).total_seconds())
        difference_ms = int((timestamp_dt - today_1336_cph).total_seconds() * 1000)
        self.send_message(
            post["channel_id"],
            f"{post['username']} is early. {difference_s} seconds ({difference_ms} milliseconds) before {today_1336_cph.strftime('%H:%M')}",
        )
        self.react_with_smiley(post['post_id'], "poop")

    def handle_message(self, post):
        try:
            message = post['message'].lower().strip()

            # Convert the post unix timestamp to Europe/Copenhagen timezone
            post_time = datetime.fromtimestamp(post['create_at']/1000).astimezone(pytz.timezone('Europe/Copenhagen'))

            # Handle the message - .test
            if message == ".test":
                message_text = f"You said {message} --- {post['channel_id']} --- {post['post_id']} --- {post_time.strftime('%Y-%m-%d %H:%M:%S')}"
                self.send_message(post['channel_id'], message_text)
                self.react_with_smiley(post['post_id'], 'smile')
            # Handle the message - 1337
            elif message == "1337" or (self.debug and message == ".testearly"):
                if self.config["FEATURE_IS_EARLY"] and message == ".testearly" or post_time.strftime("%H%M") == "1336":
                    # handle the case where the user is early
                    self.handle_early(post,post_time)
                    # lets just return here, we don't want to score points for being early
                    return
                if self.debug or post_time.strftime("%H%M") == "1337":
                    yearmonthday = post_time.strftime("%Y%m%d")
                    yearmonth = post_time.strftime("%Y%m")
                    day = post_time.strftime("%d")

                    keyday = f"{post['channel_id']}:{yearmonthday}:{post['user_id']}"
                    keyday_ms = f"speed:{post['channel_id']}:{yearmonth}:{day}:{post['user_id']}"
                    keymonth = f"{post['channel_id']}:{yearmonth}:{post['user_id']}"
                    if self.redis_client.exists(keyday):
                        self.send_message(post['channel_id'], "Sorry, you can only score points once per day.")
                        self.react_with_smiley(post['post_id'], "zany_face")
                        return

                    # Get current scores
                    today_count = self.redis_client.keys(
                        f"{post['channel_id']}:{yearmonthday}:*"
                    )
                    num_scores = len(today_count)

                    # Get the score and reaction based on today's scores
                    if num_scores < len(self.config['POINTS']) - 1: # Account for the last "too slow" entry
                        score_info = self.config['POINTS'][num_scores]
                    else:
                        score_info = self.config['POINTS'][-1] # Use the fallback entry for too slow responses

                    points = score_info['points']
                    emoji = score_info['emoji']

                    # Calculate milliseconds after 13:37:00
                    cph_tz = pytz.timezone('Europe/Copenhagen')
                    if self.debug:
                        # if debug use the time from the post instead of the current time to ensure the correct time is used
                        today_1337_cph = post_time.replace(second=0, microsecond=0)
                    else:
                        today_1337_cph = datetime.now(cph_tz).replace(
                            hour=13, minute=37, second=0, microsecond=0
                        )
                    timestamp_dt = datetime.fromtimestamp(post['create_at'] / 1000, cph_tz)
                    difference_s = round((timestamp_dt - today_1337_cph).total_seconds())
                    difference_ms = int((timestamp_dt - today_1337_cph).total_seconds() * 1000)

                    # If points are 0, it's the too slow case
                    if points == 0:
                        self.send_message(
                            post["channel_id"],
                            f"{post['username']} was too slow. {difference_s} seconds ({difference_ms} milliseconds) after {today_1337_cph.strftime('%H:%M')}",
                        )
                        return
                    else:
                        # Add daily score for the user, to keep track of daily points
                        self.redis_client.set(keyday, points)

                        # Increment monthly score for the user, to keep track of monthly points
                        self.redis_client.incrby(keymonth, points)

                        # Add the difference in milliseconds to redis to keep track of average/fastest speed
                        if difference_ms >= 0:
                            # add the daily speed
                            self.redis_client.set(keyday_ms, difference_ms)

                        # Output score message
                        self.send_message(
                            post["channel_id"],
                            f"{post['username']} scored {points} points! {difference_s} seconds ({difference_ms} milliseconds) after {today_1337_cph.strftime('%H:%M')}",
                        )

                    # React with the emoji
                    self.react_with_smiley(post["post_id"], emoji)
            # Handle the message - .score
            elif message == ".score":
                # Prepare the key name
                current_month = datetime.now().strftime('%Y%m')
                key = f"{post['channel_id']}:{current_month}:*"

                # Get all keys matching the current month
                keys = self.redis_client.keys(key)

                if keys:
                    scores = {}
                    speed = {}
                    # Calculate total scores for each user
                    for key in keys:
                        userid = key.split(':')[2]
                        speed[userid] = self.get_mental_lag_for_user_id(
                            post["channel_id"], current_month, userid
                        )  # (fastest, average)
                        score = int(self.redis_client.get(key))
                        scores[userid] = scores.get(userid, 0) + score

                    # Sort scores in descending order
                    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

                    # Generate and send the score message
                    message = 'This months scoreboard:\n'

                    for rank, (userid, score) in enumerate(sorted_scores, start=1):
                        username = self.mattermost.users.get_user(user_id=userid)['username']
                        username = username[:1] + "\u200B" + username[1:]
                        if rank <= len(self.config['POINTS']):
                            message += f":{self.config['POINTS'][rank-1]['emoji']}: {username}: {score} points (avg {speed.get(userid)[1]}ms / fastest {speed.get(userid)[0]}ms)\n"
                        else:
                            message += f":{self.config['POINTS'][-1]['emoji']}: {username}: {score} points (avg {speed.get(userid)[1]}ms / fastest {speed.get(userid)[0]}ms)\n"
                else:
                    message = "The scoreboard is empty."

                # Add last months winner
                last_month = (datetime.now() - relativedelta(months=1)).strftime('%Y%m')
                key = f"{post['channel_id']}:{last_month}:*"
                keys = self.redis_client.keys(key)
                if keys:
                    scores = {}
                    for key in keys:
                        userid = key.split(':')[2]
                        score = int(self.redis_client.get(key))
                        scores[userid] = scores.get(userid, 0) + score
                    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    # Fetch username from Mattermost
                    username = self.mattermost.users.get_user(user_id=sorted_scores[0][0])['username']
                    # Add a zero-width space to the username to prevent mentions
                    username = username[:1] + "\u200B" + username[1:]
                    message += f"\nLast months winner: {username} with {sorted_scores[0][1]} points"
                # If no winner was found, add a message
                else:
                    message += '\nNo winner last month'

                self.send_message(post['channel_id'], message)

            # Handle the message - .help
            elif message == ".help":
                self.send_message(
                    post["channel_id"],
                    "Available commands:\n1337 - Score points\n.score - Show monthly scores.",
                )
                if self.debug:
                    self.send_message(
                        post["channel_id"],
                        "Debug commands:\n\
                        .clear - Clear all keys\n\
                        .testdata - Add test data for the current and previous month\n.testjoin - Test the join message\n\
                        .testearly - Test the early message\n\
                        .testjoin - Test the join message\n\
                        ",
                    )
            elif message == ".clear":
                if self.debug:
                    # Clear all keys
                    self.redis_client.flushall()
                    self.send_message(post["channel_id"], "All keys cleared")
            elif message == ".testjoin":
                """Test the join message"""
                users = ["bottymcbotface", "chatgpt", "chatgpt-dev"]
                # get user ids and add them to the user_ids list
                user_ids = []
                for user in users:
                    user_ids.append(self.mattermost.users.get_user_by_username(user)["id"])
                # create a fake typing event for the following users
                for user_id in user_ids:
                    event = {
                        "event": "typing",
                        "data": {
                            "parent_id": "",
                            "user_id": user_id,
                        },
                        "broadcast": {
                            "omit_users": {user_id: True},
                            "user_id": "",
                            "channel_id": post["channel_id"],
                            "team_id": "",
                            "connection_id": "",
                            "omit_connection_id": "",
                        },
                        "seq": 2,
                    }
                    typing_event = TypingEvent(event, self)
                    self.handle_typing_event(typing_event)
            elif message == ".testdata":
                if not self.debug:
                    self.send_message(
                        post["channel_id"],
                        "This command is only available in debug mode",
                    )
                    return
                else:
                    self.send_message(
                        post["channel_id"],
                        "Adding test data for the current and previous month",
                    )
                import random

                users = ["bottymcbotface", "chatgpt", "chatgpt-dev"]
                # get user ids and add them to the user_ids list
                user_ids = []
                for user in users:
                    user_ids.append(
                        self.mattermost.users.get_user_by_username(user)["id"]
                    )
                # Add a test score for each user for the current month for 10 days from the beginning of the month
                # by incrementing the data and add a score for each and then adding a speed random ms for each day for the user_id as well
                yearmonthday = post_time.strftime("%Y%m%d")
                yearmonth = post_time.strftime("%Y%m")
                previous_yearmonth = (post_time - relativedelta(months=1)).strftime(
                    "%Y%m"
                )
                previous_yearmonthday = (post_time - relativedelta(months=1)).strftime(
                    "%Y%m%d"
                )
                day = post_time.strftime("%d")

                keyday = f"{post['channel_id']}:{yearmonthday}:{post['user_id']}"
                keyday_ms = (
                    f"speed:{post['channel_id']}:{yearmonth}:{day}:{post['user_id']}"
                )
                keymonth = f"{post['channel_id']}:{yearmonth}:{post['user_id']}"
                for user_id in user_ids:
                    for i in range(1, 5):
                        # current month
                        score = random.choice([15, 10, 5, 0])
                        self.redis_client.set(
                            f"{post['channel_id']}:{yearmonthday[:-1]}{i}:{user_id}",
                            score,
                        )
                        self.redis_client.incrby(
                            f"{post['channel_id']}:{yearmonth}:{user_id}", score
                        )
                        self.redis_client.set(
                            f"speed:{post['channel_id']}:{yearmonth}:0{i}:{user_id}",
                            random.randint(10, 2000),
                        )
                        # previous month
                        score = random.choice([15, 10, 5, 0])
                        self.redis_client.set(
                            f"{post['channel_id']}:{previous_yearmonthday[:-1]}{i}:{user_id}",
                            score,
                        )
                        self.redis_client.incrby(
                            f"{post['channel_id']}:{previous_yearmonth}:{user_id}",
                            score,
                        )
                        self.redis_client.set(
                            f"speed:{post['channel_id']}:{previous_yearmonth}:0{i}:{user_id}",
                            random.randint(10, 2000),
                        )
        except Exception as e:
            print(f"Error in handle_message: {e}")

    def send_message(self, channel_id, message):
        try:
            self.mattermost.posts.create_post(options={
                'channel_id': channel_id,
                'message': message,
            })
        except Exception as e:
            print(f"Error in send_message: {e}")

    def react_with_smiley(self, post_id, smiley_emoji):
        options = {
            "user_id": self.mattermost.users.get_user(user_id='me')['id'],
            "post_id": post_id,
            "emoji_name": smiley_emoji
        }
        self.mattermost.reactions.create_reaction(options)

    def get_channel(self, channel_id, no_cache=False, expire_after=60 * 60 * 25):
        """get_channel from mattermost by channel_id and cache the result in redis or fetch from redis if it exists"""
        if no_cache:
            return self.mattermost.channels.get_channel(channel_id=channel_id)
        channel = self.redis_client.get(f"channel:{channel_id}")
        if channel:
            return json.loads(channel)
        else:
            channel = self.mattermost.channels.get_channel(channel_id=channel_id)
            self.redis_client.set(
                f"channel:{channel_id}", json.dumps(channel), ex=expire_after
            )
            return channel

    def get_user(self, user_id, no_cache=False, expire_after=60 * 60 * 25):
        """get_user from mattermost by user_id and cache the result in redis or fetch from redis if it exists"""
        expire_after = 60 * 60 * 25  # 25 hours
        if no_cache:
            return self.mattermost.users.get_user(user_id=user_id)
        user = self.redis_client.get(f"user:{user_id}")
        if user:
            return json.loads(user)
        else:
            user = self.mattermost.users.get_user(user_id=user_id)
            self.redis_client.set(f"user:{user_id}", json.dumps(user), ex=expire_after)
            return user


if __name__ == "__main__":
    bot = ScoreBot()
    asyncio.run(bot.run())
