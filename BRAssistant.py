from datetime import date
import re
import asyncio
import os
import sys
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from email.message import EmailMessage

from utils.feedback_functions import get_feedback
from utils.get_patch_info import *
from utils.pkg_stats import get_package_infos
from utils.contextualizing_agent import get_relevant_chapters
from elastic_functions.search_database import *
from elastic_functions.database_sync import sync_knowledge

from ai_agents.router import get_ai_review

load_dotenv()

es = Elasticsearch("http://localhost:9200", meta_header=False)
es = es.options(headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"})
embedder = SentenceTransformer("all-MiniLM-L6-v2")

MAIL_ADRESS = os.getenv("MAIL_ADRESS", "").lower()

EML_OUTPUT_DIR = "reviews_eml/"
PATCH_DATABASE = "ressources/buildroot_lessons.jsonl"
INSTRUCTIONS_FILE = "ressources/system_instructions.txt"
AI_MODEL_USED = os.getenv("REVIEW_AI_PROVIDER", "").lower()

RE_BUMP = re.compile(r"package/\s*([^/:\s]+)\s*:\s*.*bump")
RE_SERIE = re.compile(r"\[[^\]]*?(\d+)/([2-9]|\d{2,})\]")


def review_patch(patch_url):
    series_data = ""

    if os.path.isfile(patch_url):
        patch_data = get_patch_from_file(patch_url)
        print("Local file detected, skipping Patchwork API retrieval.")
    else:
        patch_data = get_patch_from_patchwork(patch_url)
        print("Patchwork URL detected, retrieving patch data from API.")

        if not patch_data:
            print("Error: Failed to retrieve patch data.")
            return None, None
        
        is_series = re.search(RE_SERIE, patch_data['subject'])
        if is_series:
            url = input("Include previous patches of the series in the context ? (y/n): ").strip()
            if url.lower() == "y":
                series_data = "Series Context: " + get_full_series_context(patch_data['id'], patch_data['series'][0].get('id')) if patch_data.get('series') else ""

    # 1. Search in precedent patches (technical analogy)
    past_cases = search_history(embedder, es, patch_data)
    past_cases_str = "\n".join([f"CASE {i+1}: [URL: {c['source_url']}] Issue: {c['issue']} -> Action: {c['action']}\n" for i, c in enumerate(past_cases)])
    print(past_cases_str)
    # 2. Enhanced manual search (rule compliance)
    print("Identifying relevant manual chapters with the routing agent...")
    relevant_chapters = get_relevant_chapters(patch_data['diff']) 
    print(relevant_chapters)
    manual_rules = search_manual(es, relevant_chapters)
    manual_rules_str = "\n".join([f"RULE {i+1}: [{r['url']}] {r['content']}\n" for i, r in enumerate(manual_rules)])
    

    # 3. Find the last version available of a package in case of a version bump
    match = RE_BUMP.search(patch_data['subject'])
    package_last_version=""
    if match:
        package_name = match.group(1)
        package_infos = asyncio.run(get_package_infos(package_name))
        package_last_version += "Package current last version available: " + package_infos['version']
    
    # 4. Prompt with clear distinction of sources {patch_data['full_discussion']}
    user_prompt = f"""
    Date of the review: {date.today().strftime("%d/%m/%Y")}
    AI-model-used: {AI_MODEL_USED}
    
    I will provide you with context and a patch for the Buildroot project.
    Before writing the final email, you MUST use a <think> block to analyze each rule and past rejection as verification Steps.
    For each one, answer: 'Does the context of this rule match EXACTLY the context of the diff?'. If no, discard it.

    You must follow this logical flow for each potential issue:

    --- YOUR LOGICAL PROCESS ---
    STEP 0: List internally all the lines of the diff, and take into account the "Series Context" if present.
    For each change in the diff:
    STEP 1: Is there a violation of a specific 'MANUAL' rule (RULE 1, 2, 3...) ? 
    -> If YES: Quote diff line, explain, quote Manual URL. Stop.
    STEP 2: Does the issue or logic match a pattern or a technical error described in 'PAST REJECTIONS'(CASE 1, 2, 3..)?
    -> If YES: Quote diff line, explain similarity using the RAG's reasoning, and you MUST provide the source_url from that specific RAG entry. Stop.
    STEP 3: Do you suspect a technical error based on your own Expert Intuition ? 
    -> If YES: Quote diff line, suggest a change using varied polite phrasing, append [Source: Expert Intuition]. Stop.
    STEP 4: If none of the above, stay silent on this line.
    If the entire patch has no issues after these steps, reply ONLY: "Looks good to me, no issue found."

    --- CONTEXT DATA ---
      -- MANUAL RULES--
    {manual_rules_str}

      -- PAST REJECTIONS--
    {past_cases_str}

    --- PATCH DATA ---
    Subject: {patch_data['subject']}
    {package_last_version}
    Description: {patch_data['full_discussion']}
    Diff: {patch_data['diff']}
    {series_data}
    """

    try:
        with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
            system_instructions = f.read()
    except FileNotFoundError:
        print(f"Error: {INSTRUCTIONS_FILE} not found.")
        return None, None

    print(f"Analyzing patch: {patch_url}...")

    try:
        review_text, total_tokens = get_ai_review(system_instructions, user_prompt)
        # Cleaning for potential thinking blocks
        review_text =  re.sub(r'<think>.*?</think>', '', review_text, flags=re.DOTALL)
        print(f"Token usage: {total_tokens}")
        return review_text, patch_data
    except Exception as e:
        print(f"Error, can't speak to the AI model currently : {e}")
        return None, None


def save_as_eml(review_text, patch_data):
    """Generate an editable .eml file (standard mail format)."""
    msg = EmailMessage()
    msg.set_content(review_text)
    msg["Subject"] = f"Re: {patch_data['name']}"
    msg["From"] = {MAIL_ADRESS}
    msg["To"] = patch_data["submitter"]["email"], "buildroot@buildroot.org"

    msg_id = patch_data.get('msgid')
    if msg_id:
        if not msg_id.startswith('<'):
            msg_id = f"<{msg_id}>"
            
        msg['In-Reply-To'] = msg_id
        msg['References'] = msg_id

    os.makedirs(EML_OUTPUT_DIR, exist_ok=True)
    
    file_path = os.path.join(EML_OUTPUT_DIR, f"review_patch_{patch_data['id']}.eml")
    with open(file_path, "wb") as f:
        f.write(msg.as_bytes())
    print(f"Done. Review ready in {file_path}\n")


def run_agent(patch_url):
    review_text, patch_data = review_patch(patch_url)

    if review_text and patch_data:
        save_as_eml(review_text, patch_data)
        get_feedback(patch_url, review_text)

if __name__ == "__main__":
    sync_knowledge(embedder, es, PATCH_DATABASE)

    if (len(MAIL_ADRESS)<1):
        sys.exit("Error : please provide a valid mail adress in .env file.")

    print("\n--- Welcome to the Buildroot Review Assistant ---")
    print("(Type 'exit' or 'q' to stop the script)")

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            run_agent(arg)

    while True:
        url = input("Paste Patchwork URL, file path or quit (q): ").strip()
        
        if url.lower() in ['exit', 'q', 'quit']:
            print("Goodbye!")
            break
            
        if not url:
            continue
            
        run_agent(url)
