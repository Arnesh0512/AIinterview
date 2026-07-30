from datetime import datetime, timezone
from pymongo import MongoClient

# connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["test_db"]
collection = db["datetime_test"]

collection.delete_many({})  # clean collection

# datetime.max in UTC
dt_max = datetime.max.replace(tzinfo=timezone.utc)

# insert
collection.insert_one({
    "time": dt_max
})

print("Inserted:", dt_max)

# retrieve
doc = collection.find_one({})
retrieved_time = doc["time"]

print("Retrieved:", retrieved_time)

# convert retrieved to UTC aware (Mongo returns naive UTC)
retrieved_time = retrieved_time.replace(tzinfo=timezone.utc)

# compare
print("Equal to datetime.max ?", retrieved_time == dt_max)