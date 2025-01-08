from pymongo import MongoClient

# Replace <username>, <password>, and <dbname> with your actual MongoDB credentials
client = MongoClient('')

db = client
collection = db['']

# Insert a test document
result = collection.insert_one({'name': 'Test Document'})
print(f'Document inserted with ID: {result.inserted_id}')

# Retrieve the document
document = collection.find_one({'_id': result.inserted_id})
print(document)
