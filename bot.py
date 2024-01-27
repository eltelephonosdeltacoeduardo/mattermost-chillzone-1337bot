#!/bin/python3

###########################
# 1337 bot for Mattermost
###########################

# TODO: Use local time only?
# IDEA: Log 1337-text timestamp in redis for each user, for each day. Use that to calculate average speed.

import json
import asyncio
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import redis
import pytz
from dotenv import load_dotenv
from mattermostdriver import Driver

load_dotenv()

class ScoreBot:
    def __init__(self):
        # Config
        self.config = {
            'REDIS_HOST': os.getenv('REDIS_HOST'),
            'REDIS_PORT': int(os.getenv('REDIS_PORT')),
            'MATTERMOST_URL': os.getenv('MATTERMOST_URL'),
            'MATTERMOST_TOKEN': os.getenv('MATTERMOST_TOKEN'),
            'MATTERMOST_SCHEME': os.getenv('MATTERMOST_SCHEME'),
            'MATTERMOST_PORT': int(os.getenv('MATTERMOST_PORT')),
            'MATTERMOST_CHANNELS':
            [
                '1337evenmoredev',
                '1337dev',
                '1337'
            ],
            'POINTS':
            [
                {'points': 15, 'emoji': 'first_place_medal'},
                {'points': 10, 'emoji': 'second_place_medal'},
                {'points': 5, 'emoji': 'third_place_medal'},
                # Fallback entry for too slow responses (0 points and a specific emoji)
                {'points': 0, 'emoji': 'poop'}
            ]
        }

        # Redis
        self.redis_client = redis.StrictRedis(
            host=self.config['REDIS_HOST'],
            port=self.config['REDIS_PORT'],
            decode_responses=True
        )

        # Mattermost
        self.mattermost = Driver({
            'url': self.config['MATTERMOST_URL'],
            'token': self.config['MATTERMOST_TOKEN'],
            'scheme': self.config['MATTERMOST_SCHEME'],
            'port': self.config['MATTERMOST_PORT']
        })

    def run(self):
        self.mattermost.login()
        self.mattermost.init_websocket(self.event_handler)

    async def event_handler(self, event):
        try:
            message = json.loads(event)

            # Output the message to the console along with the date and time
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(message)
            print()

            if 'data' in message and 'post' in message['data']:
                post = json.loads(message['data']['post'])

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
        except Exception as e:
            print(f"Error in event_handler: {e}")

    def handle_message(self, post):
        try:
            message = post['message'].lower()

            # Convert the post unix timestamp to Europe/Copenhagen timezone
            post_time = datetime.fromtimestamp(post['create_at']/1000).astimezone(pytz.timezone('Europe/Copenhagen'))

            # Handle the message - .test
            if message == ".test":
                message_text = f"You said {message} --- {post['channel_id']} --- {post['post_id']} --- {post_time.strftime('%Y-%m-%d %H:%M:%S')}"
                self.send_message(post['channel_id'], message_text)
                self.react_with_smiley(post['post_id'], 'smile')
            # Handle the message - 1337
            elif message == "1337":
                if post_time.strftime("%H") == "13" and post_time.strftime("%M") == "37":
                #if True:
                    day = post_time.strftime("%Y%m%d")

                    keyday = f"{post['channel_id']}:{day}:{post['user_id']}"
                    keymonth = f"{post['channel_id']}:{day[:-2]}:{post['user_id']}"
                    if self.redis_client.exists(keyday):
                        self.send_message(post['channel_id'], "Sorry, you can only score points once per day.")
                        self.react_with_smiley(post['post_id'], "zany_face")
                        return

                    # Get current scores
                    today_count = self.redis_client.keys(f"{post['channel_id']}:{day}:*")
                    num_scores = len(today_count)

                    # Get the score and reaction based on today's scores
                    if num_scores < len(self.config['POINTS']) - 1: # Account for the last "too slow" entry
                        score_info = self.config['POINTS'][num_scores]
                    else:
                        score_info = self.config['POINTS'][-1] # Use the fallback entry for too slow responses

                    points = score_info['points']
                    emoji = score_info['emoji']

                    # React with the emoji
                    self.react_with_smiley(post['post_id'], emoji)

                    # If points are 0, it's the too slow case
                    if points == 0:
                        self.send_message(post['channel_id'], 'Too slow!')
                        return
                    else:
                        # Add daily score for the user, to keep track of daily points
                        self.redis_client.set(keyday, points)

                        # Increment monthly score for the user, to keep track of monthly points
                        self.redis_client.incrby(keymonth, points)

                        # Calculate milliseconds after 13:37:00
                        cph_tz = pytz.timezone('Europe/Copenhagen')
                        today_1337_cph = datetime.now(cph_tz).replace(hour=13, minute=37, second=0, microsecond=0)
                        timestamp_dt = datetime.fromtimestamp(post['create_at'] / 1000, cph_tz)
                        difference_s = round((timestamp_dt - today_1337_cph).total_seconds())
                        difference_ms = int((timestamp_dt - today_1337_cph).total_seconds() * 1000)

                        # Output score message
                        self.send_message(post['channel_id'], f"{post['username']} scored {points} points! {difference_s} seconds ({difference_ms} milliseconds) after 13:37")
                else:
                    self.send_message(post['channel_id'], "Does it look like 13:37 to you? If yes, contact your administrator and ask the person to check the NTP settings on your machine.")
                    self.react_with_smiley(post['post_id'], "poop")
            # Handle the message - .score
            elif message == ".score":
                # Prepare the key name
                current_month = datetime.now().strftime('%Y%m')
                key = f"{post['channel_id']}:{current_month}:*"

                # Get all keys matching the current month
                keys = self.redis_client.keys(key)
        
                if not keys:
                    self.send_message(post['channel_id'], 'The scoreboard is empty.')
                    return

                scores = {}

                # Calculate total scores for each user
                for key in keys:
                    userid = key.split(':')[2]
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
                        message += f":{self.config['POINTS'][rank-1]['emoji']}: {username}: {score} points\n"
                    else:
                        message += f":{self.config['POINTS'][-1]['emoji']}: {username}: {score} points\n"

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
                self.send_message(post['channel_id'], "Available commands:\n1337 - Score points\n.score - Show monthly scores")

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

if __name__ == "__main__":
    bot = ScoreBot()
    asyncio.run(bot.run())
