import sys
import json
import re
from ai_agents.router import get_ai_review, get_ai_routing

MAPPING_FILE = "ressources/sections_buildroot_manual.json"
try:
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        SECTIONS_MAPPING = json.load(f)
except FileNotFoundError:
    print(f"Error: {MAPPING_FILE} not found.")
    sys.exit(1)

def extract_json_array(text):
    """
    Extract a JSON array from any raw text.
    Useful to remove <think> tags or markdown ```json blocks.
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    match = re.search(r'\[\s*".*?\s*\]', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    
    return json.loads(text)

def get_relevant_chapters(git_diff: str) -> list:
    """
    Analyzes a git diff with an LLM and returns the list 
    of chapter numbers from the Buildroot manual to consult.
    """
    
    formatted_chapters = []
    for chapter_num, info in SECTIONS_MAPPING.items():
        titre = info["title"]
        formatted_chapters.append(f"{chapter_num}: {titre}")

    available_chapters_string = "\n".join(formatted_chapters)

    system_instruction = f"""You are an expert routing agent for Buildroot code review.
    Here are the available manual chapters:
    {available_chapters_string}

    Your task:
    Read the patch (git diff) provided by the user. Determine which specific chapters the human expert needs to read to validate this patch in detail.
    Return ONLY a valid JSON array containing from 3 to 8 relevant chapter numbers (ex: ["16.2", "18.3", "19.3"]). Add no other text.
    CRITICAL RULE 1: Always include chapter "22.5.1" in your array.
    CRITICAL RULE 2: If the patch adds a new package, a new board or new functionalities, you MUST ALWAYS include those 3 chapters : ["23", "19.1", "19.3"] in your array.
    CRITICAL RULE 3: If you see "github.com" in the diff, you MUST include chapter "18.25.4".
    CRITICAL RULE 4: If you find other pertinent chapters, do not limit yourself to ['22.5.1', '23', '19.3', '18.25.4']"""

    prompt = f"Here is the patch to analyze:\n\n{git_diff}"

    try:
        raw_response_text, token_usage = get_ai_routing(system_instruction, prompt)
        chapters_list = extract_json_array(raw_response_text)
        return chapters_list
    except Exception as e:
        print(f"Routing agent failed after retries or JSON parsing error: {e}")
        return ["22.5.1", "23"]
