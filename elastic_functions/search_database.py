def search_history(embedder, es, patch_data, threshold=0.5):
    """Search the case history using the full context."""
    
    diff_lines = patch_data['diff'].split('\n')
    changes = [
            l.strip() for l in diff_lines 
            if (l.startswith('+') or l.startswith('-')) 
            and not l.startswith('+++') 
            and not l.startswith('---')
        ]

    if not changes:
        return []
    
    # Create a rich query combining commit message and diff
    commit_intent = patch_data.get('full_discussion', patch_data.get('subject', ''))
    query_text = (
            f"Code Error: {' '.join(changes)} "
            f"Issue Context: {commit_intent}"
    )

    query_vector = embedder.encode(query_text).tolist()

    # kNN configuration with optional filter by package if detected
    knn_config = {
        "field": "text_vector",
        "query_vector": query_vector,
        "k": 5,  # Include 5 patches to give more options
        "num_candidates": 100,
    }

    response = es.search(
        index="buildroot-patches-history",
        knn=knn_config,
        source=["technical_issue", "corrective_action", "status", "package", "code_pattern"],
    )

    #similarity threshold to prevent non relevant patch submission
    es_min_score = (1.0 + threshold) / 2.0

    context = []
    for hit in response["hits"]["hits"]:

        es_score = hit["_score"]
        if es_score < es_min_score:
            continue

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


def search_manual(es, relevant_chapters: list):
    """Search the manual based on intent and code."""

    if not relevant_chapters:
            return []
    query = {
        "query": {
            "terms": {
                "chapter_number": relevant_chapters
            }
        },
        "size": 20 
    }

    try:
        results = es.search(index="buildroot-documentation", body=query)
        
        manual_rules = []
        for hit in results['hits']['hits']:
            title = hit['_source']['rule_title']
            content = hit['_source']['raw_content']
            url = hit['_source']['url']
            
            manual_rules.append({
                'url': url,
                'content': f"Section title : {title}\n{content}"
            })
        
        return manual_rules

    except Exception as e:
        print(f"Error during manual retrieval : {e}")
        return []
