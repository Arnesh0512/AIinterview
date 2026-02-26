
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from utils.reader import uri
import certifi

client = MongoClient(uri, server_api=ServerApi('1'))

user_collection = client["interview"]["users"]
summary_collection = client["interview"]["summary"]
question_collection = client["interview"]["questions"]


if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("MongoDB URI is working")
    except Exception as e:
        print("❌ Error:", e)