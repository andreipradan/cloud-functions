import logging

import requests
from bs4 import BeautifulSoup

from utils import bot, database
from utils.parsers import parse_global

SLUG = "stiri-oficiale-slug"
URL = "https://stirioficiale.ro/informatii"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_children(elements):
    return elements.find_all(True, recursive=False)


def main(*_, **__):
    response = requests.get(URL)
    response.raise_for_status()

    data = parse_article(response.text)
    db_stats = database.get_stats(SLUG)
    if db_stats and data.items() <= db_stats.items():
        logger.info("Stiri: No updates")
        return

    database.set_stats(stats=data, slug=SLUG)
    logger.info("Stiri: Completed")

    items = {data.pop("descriere"): [data.pop("url")]}
    text = parse_global(
        title=f"🔵 {data.pop('titlu')}", stats=data, items=items, emoji="❗"
    )
    bot.send_message(text)


def parse_article(text):
    soup = BeautifulSoup(text, features="html.parser")

    stats = {}
    children = get_children(soup.article.div)
    if len(children) == 4:
        header, title, desc, link = children
    elif len(children) == 5:
        header, sub_header, title, desc, link = children
        key, value = parse_sub_header(sub_header)
        stats[key] = value
    else:
        raise ValueError(
            f"Invalid number of elements in article: {children}"
        )

    date_time, author = parse_header(header)

    stats.update(
        {
            "autor": author,
            "data": date_time,
            "titlu": parse_text(title),
            "descriere": parse_text(desc),
            "url": link.a["href"],
        }
    )
    return stats


def parse_header(time_and_who):
    date_time, author = get_children(time_and_who.div)
    date, time = [parse_text(element) for element in get_children(date_time)]
    return f"{date} {time}", parse_text(author)


def parse_sub_header(element):
    key, *value = get_children(element.time)
    key = parse_text(key).replace(":", "")
    date, time, *_ = value
    return key, f"{parse_text(date)} {parse_text(time)}"


def parse_text(element):
    return element.text.strip()
