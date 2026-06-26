import os
from google import genai
from google.genai import types
import google.genai.errors as errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@retry(
    retry=retry_if_exception_type(errors.ServerError),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(f"Gemini server error, attempt {retry_state.attempt_number}... \n({retry_state.outcome.exception()})")
)
def generate_content_with_retry(client, model_id, config, contents):
    return client.models.generate_content(
        model=model_id,
        contents=contents,
        config=config
    )

def run_review(model_id, system_instructions, user_prompt):
    """
    Generate review using Gemini model.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing from environment")

    client = genai.Client(api_key=api_key)
    
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        system_instruction=system_instructions,
        temperature=0.1
    )

    response = generate_content_with_retry(client, model_id, config, user_prompt)
    
    review_text = response.text
    token_usage = response.usage_metadata.total_token_count if response.usage_metadata else 0
    
    return review_text, token_usage
