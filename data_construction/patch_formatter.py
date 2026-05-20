import json
from google import genai
from google.genai import types
from google.api_core import exceptions
import google.genai.errors as errors
import sys
import os
from dotenv import load_dotenv, find_dotenv
import time

load_dotenv(find_dotenv())

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
MODEL_ID='gemini-3.1-flash-lite-preview'
thing=0

MAX_RETRIES=5

def mean_function(thing):
    global client
    if thing%2 == 0:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    else:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY_2", ""))

def get_processed_ids(file_path):
    """Read the output file to collect already processed IDs."""
    ids = set()
    if os.path.isfile(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if 'patch_id' in data:
                        ids.add(data['patch_id'])
                except json.JSONDecodeError:
                    continue
    return ids

def synthesize_lessons(input_file="", output_path=""):
    global thing
    
    if (os.path.isfile(output_path) == False):
        output_path = "ressources/buildroot_lessons.jsonl"
    
    processed_ids = get_processed_ids(output_path)
    
    with open(input_file, 'r') as f_in, open(output_path, 'a+') as f_out:
        for line in f_in:
            entry = json.loads(line)
            
            # Skip if already processed
            patch_id = entry.get('patch_id')
            if patch_id in processed_ids:
                continue

            # Limiting diff to avoid context overflow and save tokens
            diff_snippet = entry['diff'][:1500] if entry['diff'] else "No diff available"
            
            prompt = f"""
            You are a Buildroot maintainer and senior systems engineer. 
            Analyze the following patch and discussion to extract a technical "case-law" rule.

            PATCH DATA:
            Subject: {entry['subject']}
            Status: {entry['status']}
            Diff: {diff_snippet}
            Discussion: {entry['full_discussion']}

            TASK:
            1. Identify the package name (use key: "package").
            2. CODE PATTERN: Extract the line(s) of the diff that caused the rejection. (use key: "code_pattern").
            3. TECHNICAL ISSUE: Explain why it was rejected/changed. (use key: "technical_issue").
            4. CORRECTIVE ACTION: State the rule for the contributor to follow. (use key: "corrective_action").

            Output must be a STRICT JSON object with lowercase keys.
            """

            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type='application/json',
                        )
                    )
                    
                    synthesis = json.loads(response.text)
                    synthesis['patch_id'] = patch_id
                    synthesis['status'] = entry['status']
                    synthesis['date'] = entry['date']

                    f_out.write(json.dumps(synthesis) + "\n")
                    f_out.flush()
                    
                    print(f"[{patch_id}] Synthesized - Pkg: {synthesis.get('package')}")
                    success = True
                    
                    # Rotate API keys and add a short delay
                    thing += 1
                    mean_function(thing)
                    time.sleep(1) 
                    break 
                
                except errors.APIError as e:
                    if e.code == 429:
                        print(f"Quota exceeded (429). Attempt {attempt}/5. Sleeping 60s...")
                        time.sleep(60)
                    elif e.code in [503, 504]:
                        wait = 2 ** attempt
                        print(f"Server busy or resource exhausted. Attempt {attempt}/5. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"API Error: {e}")
                        break

            if not success:
                print(f"Skipping patch {patch_id} after {MAX_RETRIES} failures.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else :
        exit("Please provide the input file path as the first argument.")

    if (os.path.isfile(input_path) == False):
        exit("Bad path provided")

    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    else :
        output_path = ""

    synthesize_lessons(input_path, output_path)
