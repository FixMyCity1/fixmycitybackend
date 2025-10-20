from pymongo import MongoClient
import os


mongo_client = MongoClient(os.getenv("MONGO_URI"))

fix_db = mongo_client["fix_db"]

issues_collection = fix_db["issues"]

users_collection = fix_db["users"]