import base64
import json
import logging
import os
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime

import requests

from utils import bot, database
from utils.parsers import parse_global

SLUG = "romania-slug"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResponseParser:
    def __init__(self, response) -> None:
        self.response = response

    def get_char(self):
        return next(self.response.iter_content(decode_unicode=True))

    def read_key(self, first=None) -> str:
        key = ""
        first = first or self.get_char()
        end = "\"" if first == "\"" else ","
        while (char := self.get_char()) != end:
            key += char
        return key

    def skip_until_today(self) -> None:
        self.get_char()  # {
        while self.read_key() != "currentDayStats":
            self.get_char()  # :
            first = self.get_char()
            if first == "{":
                depth = 1
                while depth:
                    char = self.get_char()
                    if char == "{":
                        depth += 1
                    if char == "}":
                        depth -= 1
                self.get_char()
            else:
                while self.get_char() != ",":
                    continue
        self.get_char()  # :

    def parse(self) -> str:
        self.skip_until_today()
        depth = 1
        result = self.get_char()
        while depth:
            char = self.get_char()
            if char == "{":
                depth += 1
            if char == "}":
                depth -= 1
            result += char
        return result


class Serializer:
    date_fields = ("Data",)
    deserialize_fields = "Confirmați", "Vindecați", "Decedați", "Data"
    mapped_fields = {
        "Data": "parsedOnString",
        "Confirmați": "numberInfected",
        "Vindecați": "numberCured",
        "Decedați": "numberDeceased",
        "Procent barbati": "percentageOfMen",
        "Procent femei": "percentageOfWomen",
        "Procent copii": "percentageOfChildren",
        "Vârstă medie": "averageAge",
        "Categorii de vârstă": "distributionByAge",
        "Judete": "countyInfectionsNumbers",
        "Incidență": "incidence",
        "Vaccinări": "vaccines",
        "Total doze administrate": "numberTotalDosesAdministered",
    }

    def __init__(self, response):
        self.data = OrderedDict()
        for field, api_field in self.mapped_fields.items():
            self.data[field] = response.get(api_field)

    @classmethod
    def deserialize(cls, data, fields=None):
        if not fields:
            fields = cls.deserialize_fields
        results = OrderedDict()
        for key in fields:
            results[key] = cls.deserialize_field(key, data[key])
        return results

    @classmethod
    def deserialize_field(cls, key, value):
        if key in cls.date_fields:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
        return value


def fetch_remote():
    url = os.environ["SOURCE_URL"]
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        result = ResponseParser(response).parse()
    return json.loads(result)


def main(event, context):
    data = json.loads(base64.b64decode(event['data']).decode('utf-8'))
    if not data["message"] == "fetch-current-day-stats":
        raise ValueError(f"Bad data message in {data}. Context:{context}")

    logger.info("Started checking")
    remote_data = fetch_remote()
    serializer = Serializer(remote_data)

    db_data = database.get_stats(SLUG)
    if db_data and serializer.data.items() <= db_data.items():
        msg = "Today: No updates"
        logger.info(msg)
        return

    database.set_stats(stats=serializer.data, slug=SLUG)
    logger.info("Today: Completed")

    quick_stats = Serializer.deserialize(serializer.data)
    last_updated = quick_stats.pop("Data")
    if db_data and quick_stats.items() <= db_data.items():
        msg = "No updates to quick stats"
        logger.info(msg)
        return

    bot.send_message(parse_text(quick_stats, db_data, last_updated, serializer))
    logger.info("Quick stats updated")


def parse_diff(data, old_version):
    if not old_version:
        return data
    new = deepcopy(data)
    for key in data:
        new_value, old_value = data[key], old_version.get(key)
        if old_value and new_value != old_value:
            diff = new_value - old_value if old_value else 0
            new[key] = f"{new_value} ({'+' if diff >= 0 else ''}{diff})"
    return new


def parse_text(quick_stats, db_data, last_updated, serializer):
    diff = parse_diff(quick_stats, db_data)
    diff["Actualizat la"] = last_updated

    incidence = serializer.data["Incidență"]
    infections = serializer.data["Judete"]
    items = {
        "*Incidențe*": split_in_chunks(incidence, limit=5),
        "*Infectări*": split_in_chunks(infections, limit=5),
        "*Vaccinări*": [
            f"`Total: {serializer.data['Total doze administrate']}`",
        ],
        **{
            f"*{company.title()} (24h)*": {
                "Total": f'+{data["total_administered"]}',
                "Rapel": f'+{data["immunized"]}',
            }
            for company, data in serializer.data.get(
                "Vaccinări", {}
            ).items()
            if data["total_administered"] or data["immunized"]
        },
    }
    return parse_global(
        title="🔴 Cazuri noi",
        stats=diff,
        items=items,
        footer="\nDetalii: https://coronavirus.pradan.dev/",
        emoji="🔸",
    )


def split_in_chunks(dct, chunk_size=15, limit=None):
    def chunks(lst, width):
        """Yield successive n-sized chunks from lst."""
        for i in range(width):
            yield [
                lst[i + j * width]
                for j in range(width)
                if i + j * width < len(lst)
            ]
    if not isinstance(dct, dict):
        raise ValueError("Must be instance of dict")
    if not dct:
        return
    if limit and limit < chunk_size:
        chunk_size = limit
    if len(dct) < chunk_size:
        chunk_size = len(dct)
    keys = list(reversed(sorted(dct, key=dct.get)))[:limit]
    max_key_len = len(keys[0])
    max_val_len = len(str(dct[keys[0]]))
    return [
        "  ".join(
            [
                f"`{name:<{max_key_len}}: {dct[name]:<{max_val_len}}`"
                for name in chunk
            ]
        )
        for chunk in chunks(keys, chunk_size)
    ]
