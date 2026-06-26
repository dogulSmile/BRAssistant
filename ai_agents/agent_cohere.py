import os
import cohere
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(f"Cohere API error, attempt {retry_state.attempt_number}... \n({retry_state.outcome.exception()})")
)
def generate_content_with_retry(client, model_id, system_instructions, user_prompt):
    return client.chat(
        model=model_id,
        messages=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )

def extract_text_from_cohere(response):
    """
    Manages the multiple text blocks of the model's answer.
    """
    full_text = ""
    if hasattr(response, 'message') and hasattr(response.message, 'content'):
        for block in response.message.content:
            if getattr(block, 'type', '') == 'text' and hasattr(block, 'text'):
                full_text += block.text
    return full_text

def run_review(model_id, system_instructions, user_prompt):
    """Cohere specialist for code review."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key: raise ValueError("COHERE_API_KEY missing from environment")

    client = cohere.ClientV2(api_key=api_key)
    response = generate_content_with_retry(client, model_id, system_instructions, user_prompt)

    review_text = extract_text_from_cohere(response)
    
    token_usage = 0
    if hasattr(response, 'usage') and hasattr(response.usage, 'tokens'):
        input_tokens = getattr(response.usage.tokens, 'input_tokens', 0) or 0
        output_tokens = getattr(response.usage.tokens, 'output_tokens', 0) or 0
        token_usage = input_tokens + output_tokens

    return review_text, token_usage
