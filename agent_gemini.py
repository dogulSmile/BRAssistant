from datetime import date
import json
import re
import requests
import asyncio
from elasticsearch import Elasticsearch
from scipy import stats
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from google import genai
from google.genai import types
import google.genai.errors as errors
import os
from email.message import EmailMessage
import sys
from utils.get_patch_info import *
from utils.pkg_stats import get_package_infos
from elastic_functions.search_database import *
from elastic_functions.database_sync import sync_knowledge
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

MODEL_ID = "gemini-3-flash-preview"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

es = Elasticsearch("http://localhost:9200", meta_header=False)
es = es.options(
    headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
)
embedder = SentenceTransformer("all-MiniLM-L6-v2")

EML_OUTPUT_DIR = "reviews_eml/"
PATCH_DATABASE="ressources/buildroot_lessons.jsonl"

RE_BUMP = re.compile(r"package/\s*([^/:\s]+)\s*:\s*.*bump")
RE_SERIE = re.compile(r"\[[^\]]*?(\d+)/([2-9]|\d{2,})\]")

@retry(
    retry=retry_if_exception_type(errors.ServerError),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(f"Error from the model's server, retry {retry_state.attempt_number}...")
)

def generate_review_with_retry(client, model_id, config, contents):
    return client.models.generate_content(
    model=model_id,
    contents=contents,
    config=config
)

def review_patch(patch_url):
    series_data = ""

    # 1. Analysis and RAG
    if os.path.isfile(patch_url):
        patch_data = get_patch_from_file(patch_url)
        print("Local file detected, skipping Patchwork API retrieval.")
    else:
        patch_data = get_patch_from_patchwork(patch_url)
        print("Patchwork URL detected, retrieving patch data from API.")

        if not patch_data:
            print("Failed to retrieve patch data.")
            return
        
        is_series = re.search(RE_SERIE, patch_data['subject'])
        if is_series:
            url = input("Include previous patches of the series in the context ? (y/n): ").strip()
            
            if url.lower() == "y":
                series_data = "Series Context: " + get_full_series_context(patch_data['id'], patch_data['series'][0].get('id')) if patch_data.get('series') else ""

    # 1. Enhanced precedent search (technical analogy)
    past_cases = search_history(embedder,es, patch_data)
    past_cases_str = "\n".join([f"CASE {i+1}: [URL: {c['source_url']}] Issue: {c['issue']} -> Action: {c['action']}\n" for i, c in enumerate(past_cases)])
    #print(past_cases_str)

    # 2. Enhanced manual search (rule compliance)
    manual_rules = search_manual(embedder, es, patch_data)
    manual_rules_str = "\n".join([f"RULE {i+1}: [{r['url']}] {r['content']}\n" for i, r in enumerate(manual_rules)])
    #print(manual_rules_str)

    # Find the last version available of a package in case of a version bump
    match = RE_BUMP.search(patch_data['subject'])
    package_last_version=""
    if match:
        package_name = match.group(1)
        package_infos = asyncio.run(get_package_infos(package_name))
        package_last_version+= "Package current last version available: " + package_infos['version']
    
    # 3. Prompt with clear distinction of sources {patch_data['full_discussion']}
    user_prompt = f"""
    Date of the review: {date.today().strftime("%d/%m/%Y")}
    
    I will provide you with context and a patch for the Buildroot project.
    You will perform a "Verification Step" before writing the final email, and you must follow this logical flow for each potential issue:

    --- YOUR LOGICAL PROCESS ---
    STEP 0: List internally all the lines of the diff, and take into account the "Series Context" if present.
    For each change in the diff:
    STEP 1: Is there a violation of a specific 'MANUAL' rule (RULE 1, 2, 3...) ? 
    -> If YES: Quote diff line, explain, quote Manual URL. Stop.
    STEP 2: Does the issue or logic match a pattern or a technical error described in 'PAST REJECTIONS'(CASE 1, 2, 3..)?
    -> If YES: Quote diff line, explain similarity using the RAG's reasoning, and you MUST provide the source_url from that specific RAG entry. Stop.
    STEP 3: Do you suspect a technical error based on your own Expert Intuition ? 
    -> If YES: Quote line, and include in your comment something like "I think that"/"it might"/... to show a suggestion, explain. Stop.
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

    --- FINAL FORMAT ---
        Hello {patch_data['submitter']['name']}, thanks for your patch.

        > [line from diff]
        [Comment] - [Source: Manual URL, Patch ID, or Intuition]

        Best regards,
        Buildroot Review Assistant
    """

    system_instructions = """
    ROLE: Senior Buildroot Maintainer. 

    KNOWLEDGE SOURCES:
    1. EXTERNAL_DOCS: This is the provided Manual and Past Rejections from the RAG. This is your ONLY source of truth.
    2. INTERNAL_INSTINCT: This is your pre-trained knowledge; your "Expert Intuition". You are FORBIDDEN from using this if a relevant RULE or CASE exists in EXTERNAL_DOCS.

    HIERARCHY OF TRUTH (STRICT ORDER):
    1. THE MANUAL: First, check 'OFFICIAL MANUAL RULES'. If a rule is violated, firstly read the title of the corresponding Manual Section, then explain the error and quote the rule and provide the Manual section URL.
    2. CASE-LAW: If no manual rule applies, check 'Past Rejections'. If a similar technical issue is mentioned,(even if the wording is not identical), you MUST use this as your source. It is strictly forbidden to use 'Expert Intuition' for a problem that is already documented in 'Past Rejections'. You must quote the source_url or patch_id given in the context.
    3. EXPERT INTUITION: Only if the issue is NOT in the Manual OR Past Rejections and you still suspect an important problem, as a last resort use your external knowledge. You MUST use a suggestion language like "I think that"/"it might"/... to signal speculation and quote [Source: Expert Intuition].

    STRICT QUOTATION RULES:
    1. RAG PRIORITY: For every criticism, you must look for a potential match in the given RAG. If there is one or more matches, you MUST cite the provided urls 'source_url'. 
    2. NO GENERIC LABELS: Never use "[Source: Internal Rules]" or "[Source: Expert Intuition]" if the information exists in 'Manual Rules' or 'Past Rejections'.
    3. INSTRUCTIONS QUOTATION: Do not cite 'Critical Technical Rules' or other system instructions as a source. These are your internal instructions. When applying them, use [Source: Internal Rules] if no specific Manual URL or Patch ID is available."
    
    STRICT PRINCIPLES:
    1. SILENCE IS GOLDEN: If you cannot find a CLEAR and PROVABLE violation, stay silent.
    2. INTUITION: Your 'Expert Intuition' is a suggestion, not a proven fact because you cant provide a source url in this context.
    3. EVIDENCE-BASED: Never claim something is missing without scanning the entire diff.
    4. NO ASSUMPTIONS: Never assume the content of files not visible in the diff (e.g., inside a .tar.gz). 

    CRITICAL TECHNICAL RULES:
    1. HASH POLICY: In Buildroot, when adding a new package you must provide a hash for the source. If no has is probvied in the diff, the contributor must jusitfy it.
    2. Kconfig VS Make: Understand the difference between Kconfig (Config.in) and Make (.mk). A dependency selected in Kconfig is NOT redundant in the .mk file; it is often mandatory for build ordering. Do not confuse Kconfig menu redundancy with Make build dependencies.
    3. LICENSES: Buildroot accepts both 'GPL-2.0' and 'GPL-2.0-only'. Do not request a change for this suffix unless the SPDX identifier is completely wrong (e.g. 'GPL' instead of 'GPL-2.0').
    4. PACKAGE BUMP: ONLY if the current patch's subject indicates a package bump, compare Package current last version available with the one in the subject. If they differ, ASK why the latest version isn't used.
    5. NEW PACKAGE: developers adding new packages or new boards (test suite and kernel excluded) have to register themselves in the DEVELOPERS file.
    6. ALPHABETICAL ORDER: Options in Config files and dependencies in Makefiles must be ordered alphabetically. If not, ask for reordering to improve readability and maintainability of the codebase.
    7. KERNEL BUMPS : When a patch changes a _VERSION_VALUE in a config or test file (like BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE), do not ask for a .hash file update.

    EXCEPTIONS: 
    1. For simple version bumps (package, kernel...), a description of the patch is not mandatory. In this case, this rule overrides Section 22.5.1 of the manual.("The formatting of a patch")
    2. For the summary line of the patch, do not ask for a change for small details like "bump to 1.2.3" vs "update to 1.2.3" as long as the version number is correct and the subject is clear enough.
    
    FORMAT:
    - Inline feedback only: use "> line" then your comment.
    - A Manual URL is in this format: https://buildroot.org/downloads/manual/manual.html#<id_of_the_section>
    """

    print(user_prompt)
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        system_instruction=system_instructions)

    try:
        response = generate_review_with_retry(client, MODEL_ID, config, user_prompt)
        total_tokens = response.usage_metadata.total_token_count
        print(f"Token usage: {total_tokens}")
        return response.text, patch_data
    except Exception as e:
        print(f"Error, can't speak to the AI model currently : {e}")
        return None, None


def save_as_eml(review_text, patch_data):
    """Generate an editable .eml file (standard mail format)."""
    msg = EmailMessage()
    msg.set_content(review_text)
    msg["Subject"] = f"Re: {patch_data['name']}"
    msg["From"] = "assistant@buildroot.org"
    msg["To"] = patch_data["submitter"]["email"]

    file_path = EML_OUTPUT_DIR + f"review_patch_{patch_data['id']}.eml"
    with open(file_path, "wb") as f:
        f.write(msg.as_bytes())
    print(f"Review ready in {file_path}\n")


def run_agent(patch_url):
    print(f"Analyzing patch: {patch_url}...")

    review_text, patch_data = review_patch(patch_url)

    # 2. Save as .eml
    if review_text and patch_data:
        save_as_eml(review_text, patch_data)

if __name__ == "__main__":
    sync_knowledge(embedder, es, PATCH_DATABASE)

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
