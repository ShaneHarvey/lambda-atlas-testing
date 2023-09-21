import json
import logging
import os

import pymongo
# from aws_xray_sdk.core import patch_all

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# patch_all()

client = pymongo.MongoClient(os.getenv("MONGODB_URI"), serverSelectionTimeoutMS=10000, w=1)


def lambda_handler(event, context):
    coll = client.test.test
    try:
        coll.insert_one({})
        doc = coll.find_one(projection={"_id": 1})
    except Exception as exc:
        logger.info(f"## ERROR: {exc!r}")
        raise
    return {"statusCode": 200, "body": json.dumps(doc)}
