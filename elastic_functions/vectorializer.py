from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from huggingface_hub import login
import json
import sys
import os
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

hf_token = os.getenv("HF_TOKEN", "")
if hf_token:
    login(token=hf_token, add_to_git_credential=False)
    
embedder = SentenceTransformer('all-MiniLM-L6-v2', token=hf_token)

# 2. Setup Client (ES 8.x Official Pattern)
es = Elasticsearch(
    "http://localhost:9200",
    meta_header=False,
    request_timeout=180,
    max_retries=3,
    retry_on_timeout=True
)
es = es.options(headers={
    "Accept": "application/vnd.elasticsearch+json; compatible-with=8", 
    "Content-Type": "application/json"
})

PATCHES_INDEX_NAME = "buildroot-patches-history"
DOCUMENTATION_INDEX_NAME = "buildroot-documentation"

TARGET_DOC_SECTIONS = [
    "_the_formatting_of_a_patch", "_patch_revision_changelog", "patch-policy",
    "_within_buildroot", "_format_and_licensing_of_the_package_patches", 
    "additional-patch-documentation", "writing-rules-config-in", "writing-rules-mk",
    "package-name-variable-relation", "generic-package-reference", "adding-packages-hash",
    "depends-on-vs-select", "dependencies-target-toolchain-options", "_start_script_configuration",
    "autotools-package-reference", "cmake-package-reference", "python-package-reference",
    "virtual-package-tutorial", "_package_directory", "customize-dir-structure"
]

def create_manual_index(INDEX_NAME):
    """Function 3: Initialize the index for manual rules."""
    mappings = {
        "properties": {
            "section_id": {"type": "keyword"}, # The HTML anchor (e.g. writing-rules-mk)
            "chapter": {"type": "keyword"},    # Parent chapter title
            "rule_title": {"type": "text"},    # Specific rule name
            "raw_content": {"type": "text"},   # Full text + code examples
            "url": {"type": "keyword"},        # Direct link to the section
            "text_vector": {
                "type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"
            }
        }
    }
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
    es.indices.create(index=INDEX_NAME, mappings=mappings)
    print(f"Index '{INDEX_NAME}' created.")

def create_patches_index(INDEX_NAME):
    # Official ES 8.x Mapping for kNN (HNSW index)
    # Ref: https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html
    mappings = {
        "properties": {
            "package": {"type": "keyword"},
            "category": {"type": "keyword"},
            "technical_issue": {"type": "text"},
            "corrective_action": {"type": "text"},
            "status": {"type": "text"},
            "text_vector": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine",
                "index_options": {
                    "type": "hnsw",
                    "m": 16,
                    "ef_construction": 100
                }
            }
        }
    }
    
    try:
        if es.indices.exists(index=INDEX_NAME):
            es.indices.delete(index=INDEX_NAME)
        
        # IN ES 8.x, use 'mappings' argument directly, NO 'body'
        es.indices.create(index=INDEX_NAME, mappings=mappings)
        print(f"Index '{INDEX_NAME}' created successfully.")
    except Exception as e:
        # If still 400, try to print the full response to see why
        print(f"Index creation failed: {e}")

def manual_index_to_elastic(html_path, INDEX_NAME, target_ids):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    actions = []
    for sid in target_ids:
        section_anchor = soup.find(id=sid)
        if not section_anchor: continue

        # Climb to the parent div with class "section", "chapter", or "appendix"
        container = section_anchor.find_parent("div", class_=["section", "chapter", "appendix"])
        
        if container:
            # Retrieve the title (h2, h3, or h4)
            title_tag = container.find(['h2', 'h3', 'h4', 'h5'])
            title = title_tag.get_text(strip=True) if title_tag else sid
            
            # Clean the text: replace multiple line breaks with a single one
            # to avoid visually empty "rules"
            raw_text = container.get_text(separator=" ", strip=True)
            clean_text = re.sub(r'\s+', ' ', raw_text)

            actions.append({
                "_index": INDEX_NAME,
                "_id": f"doc_{sid}",
                "_source": {
                    "section_id": sid,
                    "rule_title": title,
                    "raw_content": clean_text,
                    "url": f"https://buildroot.org/downloads/manual/manual.html#{sid}",
                    "text_vector": embedder.encode(clean_text).tolist()
                }
            })

    try:
        helpers.bulk(es, actions, chunk_size=50, request_timeout=200)
        print(f"{len(actions)} sections of the manual indexed with full content.")
    except helpers.BulkIndexError as e:
        print(f"Error during indexing of {len(e.errors)} documents : ")
        print(json.dumps(e.errors[0], indent=2))

def patches_index_to_elastic(jsonl_file, INDEX_NAME):
    actions = []
    with open(jsonl_file, 'r') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line: continue # Skip empty lines
            
            try:
                data = json.loads(line)

                patterns = data.get('code_pattern', "")
                if isinstance(patterns, list):
                    patterns = " ".join(patterns)

                combined_text = (
                    f"Package: {data.get('package', 'unknown')} "
                    f"Issue: {data['technical_issue']} "
                    f"Code Error: {patterns} "
                )
                vector = embedder.encode(combined_text).tolist()
                
                doc = {
                    "_index": INDEX_NAME,
                    "_id": f"{data.get('patch_id', i)}", 
                    "_source": {
                        "package": data.get('package', 'unknown'),
                        "technical_issue": data['technical_issue'],
                        "corrective_action": data['corrective_action'],
                        "code_pattern": patterns,
                        "status": data.get('status', 'unknown'),
                        "text_vector": vector
                    }
                }
                actions.append(doc)
            except Exception as e:
                print(f"Error processing line {i}: {e}")

    if actions:
        # Use bulk helper for efficiency
        helpers.bulk(es, actions)
        print(f"Successfully indexed {len(actions)} documents.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 <-d|-p> vectorializer.py <path_to_file> <reset (optional)> \n  -d for documentation input, -p for patches")
        sys.exit(1)
    
    input_type = sys.argv[1]
    input_path = sys.argv[2]
    reset_asked = sys.argv[3] if len(sys.argv) > 3 else "noreset"

    if input_type not in ['-d', '-p']:
        print("First argument must be -d (documentation) or -p (patches)")
        sys.exit(1)
    elif not os.path.isfile(input_path):
        print(f"Bad path provided: {input_path}")
        sys.exit(1)

    if input_type == '-d':
        if reset_asked.lower() == "reset": create_manual_index(DOCUMENTATION_INDEX_NAME)
        manual_index_to_elastic(input_path, DOCUMENTATION_INDEX_NAME, TARGET_DOC_SECTIONS)
    else:
        if reset_asked.lower() == "reset": create_patches_index(PATCHES_INDEX_NAME)
        patches_index_to_elastic(input_path, PATCHES_INDEX_NAME)
