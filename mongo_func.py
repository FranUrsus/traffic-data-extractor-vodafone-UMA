from pymongo import MongoClient
import json
import os
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("CONNECTION_STRING")


def get_database(database_name="STEP"):
    url = f'mongodb://{os.getenv("MONGO_USERNAME")}:{os.getenv("MONGO_PASSWORD")}@localhost:{os.getenv("MONGO_PORT")}'
    # Create a connection using MongoClient
    client = MongoClient(url, authSource='STEP')

    # Create the database if it doesn't exist, otherwise return the existing database
    return client[database_name]


def insert_data(collection, data):
    # Insert data into the collection
    collection.insert_one(data)


def insert_multiple_data(collection, data_list):
    # Insert multiple data into the collection
    collection.insert_many(data_list)


def insert_file(collection, file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        insert_data(collection, data)


def insert_multiple_files(collection, file_paths):
    for file_path in file_paths:
        insert_file(collection, file_path)

if __name__ == '__main__':
    print(get_database()['lineasEMT'].find_one())