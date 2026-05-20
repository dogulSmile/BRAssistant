import requests
import time
import json
import re
import sys

BASE_API = "https://patchwork.ozlabs.org/api/1.2"
PROJECT_ID = 27

state_dict = {
    "new": 1,
    "under_review": 2,
    "accepted": 3,
    "rejected": 4,
    "request_for_comments": 5,
    "not_applicable": 6,
    "changes_requested": 7
}

invert_dict = {v: k for k, v in state_dict.items()}

output_path = sys.argv[1]

def clean_comment(text):
    """Supprime les lignes de citations (>) et les signatures pour ne garder que le texte frais."""
    lines = text.split('\n')
    cleaned_lines = [l for l in lines if not l.strip().startswith('>') and len(l.strip()) > 0]
    return '\n'.join(cleaned_lines)

def get_deep_patch_data(patch_api_url):
    """Retrieve the full data of a specific patch."""
    res = requests.get(patch_api_url)
    if res.status_code != 200:
        return None
    return res.json()

def harvest_deep_lessons(max_pages=1, patch_status="*", output_file=""):
    
    if len(output_file) == 0:
        output_file = "lessons_raw.json"

    with open(output_file, "a+", encoding="utf-8") as f:

        for page in range(11, max_pages + 1):
            list_url = f"{BASE_API}/patches/?project={PROJECT_ID}&state={patch_status}&per_page=10&page={page}&order=-date"
            print(f"--- Analyse Page {page} ---")
            
            r = requests.get(list_url)
            if r.status_code != 200: break
            
            summary_list = r.json()
            
            for item in summary_list:
                
                print(f"Extraction détails patch {item['id']}...")
                full_patch = get_deep_patch_data(item['url'])
                if not full_patch: continue
                
                
                c_res = requests.get(full_patch['comments'])
                if c_res.status_code != 200: continue
                comments = c_res.json()
                
                full_discussion = []
                for comm in comments:
                    content = comm['content']
                    cleaned = clean_comment(content)
                    
                    if len(cleaned) > 50:
                        author = comm['submitter']['name']
                        full_discussion.append(f"[{author}]:\n{cleaned}")
                
                if full_discussion:
                    lesson = {
                        "patch_id": full_patch['id'],
                        "subject": full_patch['name'],
                        "diff": full_patch['diff'], 
                        "full_discussion": "\n\n".join(full_discussion), 
                        "date": full_patch['date'],
                        "status": invert_dict[patch_status]
                    }
                    f.write(json.dumps(lesson) + "\n")
                    f.flush() 
                    print(f"  [DISQUE] Patch {item['id']} sauvegardé.")
                
                time.sleep(0.5) 

harvest_deep_lessons(max_pages=20, patch_status=state_dict["rejected"], output_file=output_path)
harvest_deep_lessons(max_pages=20, patch_status=state_dict["changes_requested"], output_file=output_path)
