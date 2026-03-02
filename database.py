from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from utils.reader import uri
import gridfs
import certifi

client = MongoClient(uri, server_api=ServerApi('1'))

db = client["interview"]

candidate_collection = db["candidate"]

resume_collection = db["resume"]
resume_fs = gridfs.GridFS(db)
resume_question_collection = db["resume_question_session"]

github_collection = db["github"]
github_question_collection = db["github_question_session"]

leetcode = db["leetcode"]
coding_collection = db["coding"]
coding_question_collection = db["coding_question_session"]

concept_collection = db["concept"]
concept_question_collection = db["concept_question_session"]

if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("MongoDB URI is working")
    except Exception as e:
        print("❌ Error:", e)

