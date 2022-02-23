import os
import telegram

CHAT_ID = os.environ["CHAT_ID"]


def send_message(text):
    bot = telegram.Bot(token=os.environ["TOKEN"])
    text = text.replace("_", "\\_")
    bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        disable_notification=True,
        parse_mode=telegram.ParseMode.MARKDOWN,
    )
