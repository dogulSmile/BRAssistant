def search_history(embedder, es, patch_data):
    """Search the case history using the full context."""
    package_name = patch_data["subject"].split(":")[0].split("]")[-1].strip()
    
    diff_lines = patch_data['diff'].split('\n')
    added_content = [l[1:].strip() for l in diff_lines if l.startswith('+') and not l.startswith('+++')]

    # Create a rich query combining subject and diff
    query_text = (
        f"Package name: {package_name}\n"
        f"Subject: {patch_data['subject']}\n"
        f"Code Patterns: {' '.join(added_content[:20])}"
    )

    query_vector = embedder.encode(query_text).tolist()

    # kNN configuration with optional filter by package if detected
    knn_config = {
        "field": "text_vector",
        "query_vector": query_vector,
        "k": 5,  # Increase to 5 to give Gemini more options
        "num_candidates": 100,
    }

    # Attempt to extract the package name from the subject (e.g. [PATCH] zlib: ...)
    

    response = es.search(
        index="buildroot-patches-history",
        knn=knn_config,
        source=["technical_issue", "corrective_action", "status", "package", "code_pattern"],
    )

    context = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        patch_id = src.get("patch_id", hit.get("_id", "unknown")).replace("patch_", "")
        context.append(
            {
            "package": src.get("package"),
            "original_code_error": src.get("code_pattern"),
            "issue": src["technical_issue"],
            "action": src["corrective_action"],
            "source_url": f"https://patchwork.ozlabs.org/patch/{patch_id}/",
            "status": src.get("status")
            }
        )
    return context


def search_manual(embedder, es, patch_data):
    """Search the manual based on intent and code."""
    # Here, the full discussion is essential to understand what the developer is trying to do
    query_text = f"{patch_data['subject']} {patch_data['full_discussion']}"
    query_vector = embedder.encode(query_text).tolist()

    knn_config = {
        "field": "text_vector",
        "query_vector": query_vector,
        "k": 3,
        "num_candidates": 50,
    }

    response = es.search(
        index="buildroot-documentation",
        knn=knn_config,
        source=["rule_title", "raw_content", "url"],
    )

    rules = []
    for hit in response["hits"]["hits"]:
        rules.append(
            {
                "title": hit["_source"]["rule_title"],
                "content": hit["_source"]["raw_content"],
                "url": hit["_source"]["url"],
            }
        )
    return rules
