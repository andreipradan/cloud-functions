import os

from pymongo import MongoClient

COLLECTION = "romania-collection"


def get_collection():
    return MongoClient(host=os.environ["MONGO_DB_HOST"])["telegrambot_db_prod"][COLLECTION]


def get_stats(slug):
    stats = get_collection().find_one({"slug": slug})
    if stats:
        stats.pop("_id")
        stats.pop("slug", None)
    return stats


def set_stats(stats, slug):
    update_params = {
        "filter": {"slug": slug},
        "update": {"$set": stats},
        "upsert": True,
    }
    return get_collection().update_one(**update_params)
