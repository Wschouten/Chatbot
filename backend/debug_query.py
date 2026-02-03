from rag_engine import RagEngine

print("--- Debugging Specific Query ---")
rag = RagEngine()

query = "Ik heb een product gekocht bij het tuincentrum, kan ik dat via jullie website retourneren?"
print(f"Query: {query}")

try:
    print("\n1. Generating Embedding...")
    query_emb = rag.openai_client.embeddings.create(input=query, model="text-embedding-3-small").data[0].embedding
    
    print("\n2. Querying Collection (Top 5)...")
    results = rag.collection.query(query_embeddings=[query_emb], n_results=5)
    
    print("\n3. Results found:")
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        dist = results['distances'][0][i]
        source = meta.get('source', 'unknown')
        chunk_id = meta.get('chunk', '?')
        print(f"\nResult #{i+1} (Score: {dist:.4f}) | Source: {source} (Chunk {chunk_id})")
        print(f"Content Snippet: {doc[:150]}...") 

    print("\n4. Scanning ALL chunks for keyword 'tuincentrum'...")
    all_docs = rag.collection.get()
    found = False
    for i, doc in enumerate(all_docs['documents']):
        if 'tuincentrum' in doc.lower():
            found = True
            print(f"\n--- FOUND MATCH in Chunk {all_docs['ids'][i]} ---")
            print(f"Content: {doc}")
            
    if not found:
        print("Keyword 'tuincentrum' NOT found in any chunk.")
        
except Exception as e:
    print(f"Error: {e}")

print("\n--- End Debug ---")
