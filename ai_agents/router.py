import os

from . import agent_openrouter
from . import agent_cohere
from . import agent_gemini
from . import agent_github

def get_ai_review(system_instructions, user_prompt, provider_override=None):
    """
    Read .env, choose the right agent and execute the review.
    """
    provider = provider_override or os.getenv("REVIEW_AI_PROVIDER", "").lower()
    
    if provider == "gemini":
        model_id = os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")
        return agent_gemini.run_review(model_id, system_instructions, user_prompt)
        
    elif provider == "github_models":
        model_id = os.getenv("GITHUB_MODEL_ID", "Meta-Llama-3.1-405B-Instruct")
        return agent_github.run_review(model_id, system_instructions, user_prompt)

    elif provider == "cohere":
        model_id = os.getenv("COHERE_MODEL_ID", "command-a-plus-05-2026")
        return agent_cohere.run_review(model_id, system_instructions, user_prompt)
    
    elif provider == "openrouter":
        model_id = os.getenv("OPENROUTER_MODEL_ID", "nousresearch/hermes-3-llama-3.1-405b:free") 
        return agent_openrouter.run_review(model_id, system_instructions, user_prompt)
    
    else:
        raise ValueError(f"Unknown REVIEW_AI_PROVIDER: {provider}. \nAvailable models: 'gemini', 'github_models', 'cohere'.")

def get_ai_routing(system_instructions, user_prompt):
    """Choose which AI provider to use for the routing of manual's sections."""
    provider = os.getenv("ROUTER_AI_PROVIDER", "gemini").lower()
    
    if provider == "gemini":
        model_id = os.getenv("CONTEXTUALIZING_MODEL_ID", "gemini-3.5-flash")
        return agent_gemini.run_review(model_id, system_instructions, user_prompt)

    elif provider == "gemini_lite":
        model_id = os.getenv("CONTEXTUALIZING_MODEL_ID", "gemini-3.1-flash-lite")
        return agent_gemini.run_review(model_id, system_instructions, user_prompt)
        
    elif provider == "github_models":
        model_id = os.getenv("CONTEXTUALIZING_MODEL_ID", "gpt-4o-mini") 
        return agent_github.run_review(model_id, system_instructions, user_prompt)
        
    elif provider == "cohere":
        model_id = os.getenv("CONTEXTUALIZING_MODEL_ID", "command-r7b-12-2024") 
        return agent_cohere.run_review(model_id, system_instructions, user_prompt)

    else:
        raise ValueError(f"REVIEW_AI_PROVIDER unknown : {provider}")
