from pymongo import MongoClient

# 1. Connect to your MongoDB cluster
client = MongoClient("mongodb+srv://arnesh052006:IEEEinterview@cluster.m7y1vxr.mongodb.net/?appName=Cluster")

# 2. Select your database name
db = client["interview"]

print("Starting migration: replacing 'question_number' with 'question_id' and converting values to int...\n")

# Get list of all collection names in the 'interview' database
collection_names = db.list_collection_names()

total_updated_docs = 0

# Helper function to recursively traverse and update dictionary/list structures
def update_question_keys(node):
    updated = False
    if isinstance(node, dict):
        # Check keys at the current dictionary level
        keys_to_change = []
        for k, v in node.items():
            if k == "question_number":
                keys_to_change.append(k)
            else:
                if update_question_keys(v):
                    updated = True
        
        # Perform key renaming and value type conversion
        for k in keys_to_change:
            val = node.pop(k)
            # Convert value to int if it's a string or can be cast, otherwise keep as is
            try:
                val = int(val)
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails
            
            node["question_id"] = val
            updated = True
            
    elif isinstance(node, list):
        for item in node:
            if update_question_keys(item):
                updated = True
                
    return updated

# 3. Iterate through each collection
for coll_name in collection_names:
    # Skip the leetcode collection as requested
    if coll_name == "leetcode":
        continue
        
    collection = db[coll_name]
    coll_updates = 0
    
    # 4. Traverse every document in the collection
    for doc in collection.find():
        doc_id = doc["_id"]
        # Make a deep copy/modification check
        if update_question_keys(doc):
            # Replace the document in MongoDB with the updated fields
            collection.replace_one({"_id": doc_id}, doc)
            coll_updates += 1
            total_updated_docs += 1

    print(f"Collection '{coll_name}': Updated {coll_updates} documents.")

print("\n" + "=" * 40)
print(f"Migration Complete! Total documents modified: {total_updated_docs}")
print("=" * 40)