import os
from openai import OpenAI, RateLimitError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Available models in GitHub's Azure OpenAI deployment (limited to 8k tokens input for now):
#  - azureml://registries/azure-openai/models/gpt-4o-mini/versions/1
#  - azureml://registries/azure-openai/models/gpt-4o/versions/2
#  - azureml://registries/azure-openai/models/text-embedding-3-large/versions/1
#  - azureml://registries/azure-openai/models/text-embedding-3-small/versions/1
#  - azureml://registries/azureml-cohere/models/Cohere-embed-v3-english/versions/3
#  - azureml://registries/azureml-cohere/models/Cohere-embed-v3-multilingual/versions/3
#  - azureml://registries/azureml-meta/models/Meta-Llama-3.1-405B-Instruct/versions/1
#  - azureml://registries/azureml-meta/models/Meta-Llama-3.1-8B-Instruct/versions/1

@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(f"GitHub API error, attempt {retry_state.attempt_number}... \n({retry_state.outcome.exception()})")
)
def generate_content_with_retry(client, model_id, messages):
    return client.chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=0.1,
        max_tokens=4096
    )

def run_review(model_id, system_instructions, user_prompt):
    """
    GitHub Models specialist (OpenAI compatible).
    """
    github_token = os.getenv("GITHUB_API_KEY")
    if not github_token:
        raise ValueError("GITHUB_API_KEY missing from environment to use GitHub Models")

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com", 
        api_key=github_token,
    )
    
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_prompt}
    ]

    response = generate_content_with_retry(client, model_id, messages)
    
    review_text = response.choices[0].message.content
    token_usage = response.usage.total_tokens if response.usage else 0
    
    return review_text, token_usage
