import os

import pymongo.database

mongo_client = pymongo.MongoClient(host=os.getenv('MONGO_ADDRESS'), port=27017)
db: pymongo.database.Database = mongo_client.example_app
