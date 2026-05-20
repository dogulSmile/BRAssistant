from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from huggingface_hub import login
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

hf_token = os.getenv("HF_TOKEN", "")
embedder = SentenceTransformer('all-MiniLM-L6-v2', token=hf_token)

# 2. Setup Client (ES 8.x Official Pattern)
es = Elasticsearch(
    "http://localhost:9200",
    meta_header=False
)
es = es.options(headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8", 
                         "Content-Type": "application/json"})

INDEX_NAME = "buildroot-patches-history"

def search_advice(query_text, package_filter=None):
    # Vectorize the user's query
    query_vector = embedder.encode(query_text).tolist()
    
    # Official kNN search structure for ES 8.x
    knn_config = {
        "field": "text_vector",
        "query_vector": query_vector,
        "k": 3,
        "num_candidates": 50
    }

    # If you want to filter by package (Hybrid Search)
    if package_filter:
        knn_config["filter"] = {
            "term": {"package": package_filter}
        }

    try:
        # Notice we pass 'knn' as a top-level parameter
        response = es.search(
            index=INDEX_NAME, 
            knn=knn_config,
            source=["technical_issue", "corrective_action", "status", "package"] # Return only what's needed
        )

        print(f"--- Results for: '{query_text}' ---\n")
        
        for hit in response['hits']['hits']:
            score = hit['_score']
            source = hit['_source']
            
            # Map numeric status back to readable text if you like
            status_label = "Rejected" if source['status'] == 4 else "Changes Requested"
            
            print(f"[{status_label}] (Score: {score:.2f})")
            print(f"Package: {source.get('package', 'N/A')}")
            print(f"technical_issue: {source['technical_issue']}")
            print(f"corrective_action: {source['corrective_action']}")
            print("-" * 30)

    except Exception as e:
        print(f"Search failed: {e}")

# Example Usage
#search_advice("forgotten license hash")
