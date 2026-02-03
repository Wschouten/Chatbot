import chromadb
import os

# Define the path to the persistent DB
PERSIST_DIRECTORY = "./chroma_db"

print(f"Checking ChromaDB at {PERSIST_DIRECTORY}...")

if not os.path.exists(PERSIST_DIRECTORY):
    print("ERROR: ChromaDB directory not found!")
    exit()

try:
    client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
    collection = client.get_collection("groundcover_docs")
    
    count = collection.count()
    print(f"Total Documents in Collection: {count}")
    
    if count == 0:
        print("WARNING: Collection is empty.")
    else:
        # Get first 5 documents
        data = collection.peek(limit=5)
        print("\n--- Sample Document 1 ---")
        if data['documents']:
            print(data['documents'][0])
        else:
            print("No documents found in peek?")
            
        print("\n--- IDs Present ---")
        print(data['ids'])

except Exception as e:
    print(f"An error occurred: {e}")
