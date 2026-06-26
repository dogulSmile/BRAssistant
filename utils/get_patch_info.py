import time
import requests
import re
import os

def get_full_series_context(current_patch_id, series_id):
    """
    Build a textual summary of the cover letter and previous patches.
    """
    series_api_url = f"https://patchwork.ozlabs.org/api/series/{series_id}/"
    series_json = requests.get(series_api_url).json()
    
    full_context = ""

    # 1. Retrieve the Cover Letter (0/n)
    if series_json.get("cover_letter"):
        cover_url = series_json["cover_letter"]["url"]
        cover_data = requests.get(cover_url).json()
        full_context += f"--- SERIES COVER LETTER (0/n) ---\n"
        full_context += f"Subject: {cover_data['name']}\n"
        full_context += f"Description: {cover_data['content']}\n\n"

    # 2. Retrieve previous patches (1/n up to current-1)
    full_context += "--- PREVIOUS CHANGES IN THIS SERIES ---\n"
    for p_info in series_json.get("patches", []):
        if p_info['id'] == current_patch_id:
            break  # Stop before the current patch
        
        prev_patch_data = get_patch_from_patchwork(p_info['web_url'])
        if prev_patch_data:
            full_context += f"Subject: {prev_patch_data['subject']}:\n"
            # Only include the discussion/description to save tokens,
            # the full diff of previous patches is often too heavy.
            full_context += f"Intent: {prev_patch_data['full_discussion']}\n"
            full_context += "-" * 30 + "\n"
            
    return full_context

def get_patch_from_patchwork(patch_url_or_id):
    """Retrieve all the info from the current patch, commit message inclued."""
    identifier = str(patch_url_or_id).strip('/')
    
    # 1. Extract the identifier from the URL
    if "patchwork.ozlabs.org" in identifier:
        match = re.search(r'/patch/([^/]+)', identifier)
        if match:
            identifier = match.group(1)
        else:
            raise ValueError(f"URL unknown : {patch_url_or_id}")

    # 2. Resolve the actual numeric ID
    target_id = None
    if identifier.isdigit():
        target_id = identifier
    else:
        # Search by Message-ID to find the numeric ID
        search_url = f"https://patchwork.ozlabs.org/api/1.2/patches/?msgid={identifier}"
        for attempt in range(3):
            try:
                res = requests.get(search_url, timeout=15)
                res.raise_for_status()
                search_data = res.json()
                break

            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    print(f"Error during search of Message ID : {e}")
                    return None
        
        if isinstance(search_data, list) and len(search_data) > 0:
            target_id = search_data[0]['id']
        else:
            print(f"No patch found for Message-ID : {identifier}")
            return None

    # 3. Retrieve detailed data (required for the diff)
    # This request on the specific ID contains the 'diff' field
    api_detail_url = f"https://patchwork.ozlabs.org/api/1.2/patches/{target_id}/"
    
    try:
        print(f"  -> Fetching full patch detail for ID: {target_id}")
        response = requests.get(api_detail_url, timeout=15)
        response.raise_for_status()
        patch_json = response.json()

        # 4. Retrieve potential answers of maintainers
        r_comments = requests.get(f"{api_detail_url}comments/")
        comments_json = r_comments.json() if r_comments.status_code == 200 else []

        # 5. Format the result for the agent : contributor's commit message + potential answers
        full_discussion = f"INITIAL DESCRIPTION:\n{patch_json.get('content', '')}\n\n"
        if comments_json:
            full_discussion += "MAILING LIST DISCUSSION:\n"
            for comment in comments_json:
                name = comment.get('submitter', {}).get('name', 'Unknown')
                full_discussion += f"--- Comment by {name} ---\n{comment.get('content', '')}\n\n"

        # Check if the diff is present this time
        diff_content = patch_json.get('diff')
        if not diff_content:
            print(f"Warning : no diff found in {target_id}")

        return {
            "id": target_id,
            "name": patch_json.get('name'),
            "subject": patch_json.get('name'),
            "msgid": patch_json.get('msgid'),
            "diff": diff_content,
            "status": patch_json.get('state'),
            "submitter": {
                "name": patch_json['submitter'].get('name'),
                "email": patch_json['submitter'].get('email')
            },
            "full_discussion": full_discussion,
            "patch_url": patch_json.get('web_url', f"https://patchwork.ozlabs.org/patch/{target_id}/"),
            "series": patch_json.get('series')
        }

    except Exception as e:
        print(f"Patchwork error while retrieving details on patch ({target_id}): {e}")
        return None


def get_patch_from_file(file_path):
    """
    Extract data from a local .patch file.
    Simulate the Patchwork API structure for compatibility with the agent.
    """
    if not os.path.isfile(file_path):
        print(f"'Can't find file : {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Extract the subject (Subject: [PATCH] ...)
        patch_id_match = re.search(r'^X-Patchwork-Id: (.*)', content, re.MULTILINE)
        patch_id = patch_id_match.group(1) if patch_id_match else "unknown"

        subject_match = re.search(r'^Subject: (.*?)\n(?=[^\s])', content, re.MULTILINE | re.DOTALL)
        if subject_match:
            subject = re.sub(r'\n\s+', ' ', subject_match.group(1)).strip()
        else:
            subject = "No subject found"
    
        from_match = re.search(r'^From: (.*) <(.*)>', content, re.MULTILINE)
        submitter_name = from_match.group(1) if from_match else "Unknown"
        submitter_email = from_match.group(2) if from_match else "unknown@example.com"

        description_pattern = r'Sender:.*?\n(.*)\n---\s*\n.*$'
        match = re.search(description_pattern, content, re.DOTALL | re.MULTILINE)
        description="No description found"
        if match:
            description = match.group(1).strip()

        # Try to isolate the pure diff (starting with diff --git)
        diff_match = re.search(r'(diff --git.*)', content, re.DOTALL)
        diff_content = diff_match.group(1) if diff_match else ""

        #message id to reply to it
        msgid_match = re.search(r'^Message-Id:\s*(<.*?>)', content, re.MULTILINE | re.IGNORECASE)
        msgid = msgid_match.group(1) if msgid_match else None

        return {
            "id": patch_id,
            "name": subject,
            "subject": subject,
            "msgid": msgid,
            "diff": diff_content,
            "status": "local",
            "submitter": {
                "name": submitter_name,
                "email": submitter_email
            },
            "full_discussion": description,
            "patch_url": f"https://patchwork.ozlabs.org/patch/{patch_id}/"
        }
    
    except Exception as e:
        print(f"'Error while reading patch file : {e}")
        return None
