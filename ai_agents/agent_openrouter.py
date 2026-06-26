import os
from openai import OpenAI, RateLimitError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(f"OpenRouter API error, attempt {retry_state.attempt_number}... \n({retry_state.outcome.exception()})")
)
def generate_content_with_retry(client, model_id, messages, response_format=None):
    kwargs = {"model": model_id, "messages": messages, "temperature": 0.1, "reasoning_effort": "high", "max_tokens": 8192}
    if response_format: kwargs["response_format"] = response_format
    return client.chat.completions.create(**kwargs)

def run_review(model_id, system_instructions, user_prompt):
    """OpenRouter specialist for review (Free Large Context)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: raise ValueError("OPENROUTER_API_KEY missing")

    # Standard connector pointing to OpenRouter
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    messages = [{"role": "system", "content": system_instructions}, {"role": "user", "content": user_prompt}]
    
    response = generate_content_with_retry(client, model_id, messages)
    return response.choices[0].message.content, (response.usage.total_tokens if response.usage else 0)
