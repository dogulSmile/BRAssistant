import requests
import json
import os

WEBHOOK_URL="https://hook.eu1.make.com/h4c3ca3dnz8byg5rxcm24nu5udtddvwt"

def get_feedback(patch_url, ai_snippet):
    """Ask for the user feedback on the AI's review."""

    feedback = input("""\nHow was this review ? (empty to skip) 
    [1] Perfect
    [2] Good, but missed something
    [3] Hallucination / Bad rule applied : """).strip()
    
    match feedback:
        case "1":
            return;
        case "2" | "3":
            correction = input("What should the AI have done ? : ").strip()
        case _:
            return

    if correction and correction != "" and len(correction) > 5 :
        send_feedback_to_github(patch_url, ai_snippet, correction)
    
def send_feedback_to_github(patch_url, ai_snippet, user_correction):
    """Creates a GitHub issue in the BRAssistant repository with the feedback from the user, to help improve the RAG database and the model's performance."""

    issue_title = f"[AI Feedback] Review suggestion"
    
    issue_body = f"""## AI Review Feedback\n### Patch:\n{patch_url}\n### What BRAssistant said:\n""" + \
    f"""> {ai_snippet.replace('\n', '\n>')}\n### Maintainer Correction:\n{user_correction}\n\n---\n*Vote with 👍 or 👎 to help improve the RAG database.*"""

    content = {
        "title": issue_title,
        "body": issue_body
    }

    payload_body = { "body": json.dumps(content)}

    try:
        response = requests.post(WEBHOOK_URL, json=payload_body)
        
        if response.status_code in [200, 201, 202]:
            print("\nThanks, your feedback has been sent successfully.")
        else:
            print(f"\nFailed to send feedback. Status code: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"\nAn error occurred while sending feedback: {e}")
