from pymongo import MongoClient
from bson import ObjectId

# connect
client = MongoClient("mongodb://localhost:27017")
db = client["test_db"]
col = db["test_col"]

# clean collection
col.delete_many({})

session_id = ObjectId()
timestamp = "2026-03-07T18:30:00"

print("Original ObjectId:", session_id)
print("Type:", type(session_id))

# Case 1: ObjectId as key
doc1 = {
    session_id: timestamp
}

# Case 2: string key
doc2 = {
    str(session_id): timestamp
}

# Case 3: f-string
doc3 = {
    f"{session_id}": timestamp
}

print("\nLocal Python dicts:")
print("doc1:", doc1)
print("doc2:", doc2)
print("doc3:", doc3)

# insert documents
col.insert_one({"case": "objectid_key", "data": doc1})
col.insert_one({"case": "string_key", "data": doc2})
col.insert_one({"case": "fstring_key", "data": doc3})

print("\nDocuments stored in MongoDB:\n")

for d in col.find({}, {"_id": 0}):
    print(d)