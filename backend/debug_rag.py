from rag_engine import RagEngine

print("--- Starting RAG Debug ---")
rag = RagEngine()

print("\n1. Checking Collection Count...")
try:
    count = rag.collection.count()
    print(f"Total Documents in DB: {count}")
except Exception as e:
    print(f"Error checking count: {e}")

print("\n2. Peeking at Data...")
try:
    peek = rag.collection.peek(limit=1)
    if peek and peek['documents']:
        print(f"Sample Document snippet: {peek['documents'][0][:100]}...")
        print(f"Source metadata: {peek['metadatas'][0]}")
    else:
        print("Database is empty or peek failed.")
except Exception as e:
    print(f"Error peeking: {e}")

print("\n3. Testing Query...")
query = "welke ecostyle producten zijn er allemaal?"
print(f"Query: {query}")
try:
    # Manual query to see raw results
    query_emb = rag.openai_client.embeddings.create(input=query, model="text-embedding-3-small").data[0].embedding
    results = rag.collection.query(query_embeddings=[query_emb], n_results=3)
    print(f"Raw Search Results: {results['documents']}")
except Exception as e:
    print(f"Search failed: {e}")

print("\n--- End Debug ---")
