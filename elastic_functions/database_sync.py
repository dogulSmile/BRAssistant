import os
import json

def sync_knowledge(embedder, es, jsonl_path, index_name="buildroot-patches-history"):
    """Check and index new patches from the JSONL file at startup."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir) 
    jsonl_path = os.path.join(project_root, jsonl_path)

    if not os.path.exists(jsonl_path):
        print(f"Warning: {jsonl_path} not found. Skipping sync.")
        return

    print(f"Syncing knowledge from {jsonl_path}...")
    
    # 1. Retrieve already indexed IDs to avoid unnecessary work
    try:
        # Retrieve existing IDs through a simple query
        res = es.search(index=index_name, source=False, size=10000)
        indexed_ids = {hit["_id"] for hit in res["hits"]["hits"]}
    except Exception:
        indexed_ids = set()

    new_entries = []
    with open(jsonl_path, 'r') as f:
        for line in f:
            entry = json.loads(line)
            # Use the patch ID as the Elasticsearch ID for uniqueness
            doc_id = f"patch_{entry['patch_id']}"
            
            if doc_id not in indexed_ids:
                # Prepare the text for the vector embedding
                text_to_embed = f"Issue: {entry['technical_issue']} Action: {entry['corrective_action']}"
                vector = embedder.encode(text_to_embed).tolist()
                
                # Build the document
                doc = {
                    "package": entry.get("package"),
                    "category": entry.get("category"),
                    "technical_issue": entry["technical_issue"],
                    "corrective_action": entry["corrective_action"],
                    "status": entry.get("status"),
                    "text_vector": vector
                }
                
                # Add to the indexing list
                es.index(index=index_name, id=doc_id, document=doc)
                new_entries.append(entry['patch_id'])

    if new_entries:
        print(f"Successfully indexed {len(new_entries)} new lessons.")
        es.indices.refresh(index=index_name)
    else:
        print("Knowledge base is already up to date.")
