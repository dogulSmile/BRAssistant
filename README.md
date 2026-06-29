# Buildroot Review Assistant

An AI-powered automated code review assistant designed specifically for the **Buildroot** project. The system leverages Retrieval-Augmented Generation (RAG) by combining an **Elasticsearch** vector database with an AI agent (here **Gemini 3 Flash (Thinking Mode)**) to analyze patches, enforce manual compliance, cross-reference historical rejections (jurisprudence), and handle complex multi-part patch series.



## 1. Key Features

* **Dual-Engine RAG**: Performs semantic kNN vector searches over both the official Buildroot User Manual and a curated history of past patch rejections.
* **Code-Signature Alignment**: Employs a unified embedding strategy to match raw patch diff patterns directly with natural language developer logs.
* **Patchwork Series Awareness**: Automatically detects patch structures (e.g., `[v5, 2/5]`), securely querying the Patchwork API to pull and reconstruct the context of the series' Cover Letter ($0/n$) and previous patches before reviewing the target file.
* **Strict Hierarchy of Truth**: Validates submissions through an ordered priority loop: Manual Rules $\\rightarrow$ Past Case-Law $\\rightarrow$ Expert Intuition.
* **Production-Ready Output**: Generates editable standard `.eml` mail draft reviews containing precise, inline file feedback.



## 2. Prerequisites

Ensure your host machine has the following prerequisites installed:
* **Python 3.10** or higher
* **Docker** & Docker Engine
* `curl` (for database verification)



## 3. Technical Stack & Dependencies

The project relies on the core dependencies specified in `requirements.txt`:

| Package | Purpose |
| :--- | :--- |
| `elasticsearch` (< 9.0.0) | Official client library for database interactions and vector storage. |
| `sentence-transformers` | Generates text embeddings locally for semantic search. |
| `huggingface_hub` | Manages download and caching of NLP models. |
| `bs4` (BeautifulSoup) | Handles HTML/XML log parsing and text extraction. |
| `python-dotenv` | Loads configuration options seamlessly from `.env` files. |
| `openrouter` / `google-genai` / ... | Interface tool for LLM inference APIs. |
| `asyncio` / `aiohttp` | Core asynchronous engines for concurrent network and file operations. |
| `tenacity` | Advanced retry handling for robust API calls and database synchronization. |



## 4. Infrastructure Setup

The processing pipeline requires an active Elasticsearch 8.x instance to store embeddings.

### Option A: Docker Deployment (Recommended)

Run the following command to spin up a single-node Elasticsearch container with security features disabled for development purposes:

```bash
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.12.0

docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0

docker start elasticsearch
```

### Option B: Host Systemd Service

If Elasticsearch is installed directly on the host system, manage the service using systemd outside of any Python virtual environment (outside venv):

```bash
# Check service status
sudo systemctl status elasticsearch

# Start service if stopped
sudo systemctl start elasticsearch
```

### Verifying Elasticsearch Status

Verify that the cluster is up and inspect available indices (including document counts and store sizes) using the following `curl` command:

```bash
curl -s "http://localhost:9200/"
```
Please also verify that your disk usage is below 85% or you might have indexation problems (see https://www.elastic.co/docs/troubleshoot/elasticsearch/fix-watermark-errors) :

```bash
curl -s "http://localhost:9200/_cat/allocation?v"
```


## 5. Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dogulSmile/BRAssistant
   cd BRAssistant
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Environment Variables (.env file) :**

   Fristly provide the mail adress you will use for reviews:
      ```env
      MAIL_ADRESS="vacation@gmail.com"
      ```

   Then get your keys here (no specific permissions required) :

      https://huggingface.co/settings/tokens (`HF_API_KEY` required if you want to vectorize new data)

      https://openrouter.ai/workspaces/default/keys (if using openrouter for patch reviews)
      
   You will then create/modify a `.env` file in the root directory to store your API keys and configurations, here is an example configuration with multiple AI models ready to be tested :

   ```env
      MAIL_ADRESS="vacation@gmail.com"

      HF_API_KEY="my_secret_key"
      REVIEW_AI_PROVIDER="openrouter" # gemini, github_models, cohere, openrouter...
      ROUTER_AI_PROVIDER="github_models" # gemini, gemini_lite, github_models, cohere,...

      OPENROUTER_MODEL_ID="deepseek/deepseek-v4-pro"
      OPENROUTER_API_KEY="67"

      GITHUB_MODEL_ID="gpt-4o" # or Meta-Llama-3.1-405B-Instruct
      GITHUB_API_KEY="too_expensive_to_be_shared"

      GEMINI_MODEL_ID="gemini-3.5-flash"
      GEMINI_API_KEY=""

      COHERE_MODEL_ID="command-a-plus-05-2026"
      COHERE_API_KEY=""
   ```

   As you can see, you can setup different keys/model in the `.env` file, but you will have to choose which one to use for 

   - **vectorizing** : the only provider supported at the moment is Hugging Face. just put your key in `HF_API_KEY` if you want to add new data to the RAG database.
   - **routing** :  currently the suppported models for routing are gemini, gemini_lite, github_models and cohere. Choose the provider (with the help of section "8. How to choose the AI Model"), and write it in the `ROUTER_AI_PROVIDER` variable. If you want to modify the specific model used for the routing agent, you will have to modify ai_agents/router.py
   - **patch review** : same principle, but you can choose which model to use by modifying `<PROVIDER>_MODEL_ID` in the `.env`, and write the coresponding provider in `REVIEW_AI_PROVIDER` (available ones : openrouter, gemini, github_models, cohere).


4. **Environment Variables:**

   Launch those 2 commands at the root of the project to initialize the database (Elasticsearch must be started):
   ```bash
   python3 elastic_functions/vectorializer.py -d ressources/The_Buildroot_user_manual.html reset
   python3 elastic_functions/vectorializer.py -p ressources/buildroot_lessons.jsonl reset

   (You can enhance the database by adding other files (without the 'reset'), but the format has to be respected.)
   ```



## 6. Usage

To launch the agent, please verify that your venv is activated, then in the root of the project simply launch this command :

```bash
python3 ./BRAssistant.py 
```
You will be asked to put the patch to review, you have 2 possible choices:
  - file : simply put the path of the .patch to analyze (ex: /home/user/Downloads/package-test.patch)
  - link : paste the patchwork url of the patch (ex: https://patchwork.ozlabs.org/project/buildroot/patch/20260520092415.665898-1-giulio.benetti@benettiengineering.com/)

You can also directly indicate the patch to analyze this way:

```bash
python3 ./BRAssistant.py <patchwork_url_of_the_contribution>
```

After the analyze, you will find your review ready in .eml format in the reviews_eml/ directory, you can open it with your favorite mail software and edit it (using Thunderbird, you will do right-clic, then 'Edit as new message')
Depending of your mail app, some of them are not compatible with "In-Reply-To" header, in this case you might directly reply to the original mail to keep the thread.

### Feedback

To help improve the assistant's accuracy, you can submit your feedback after each review.
Simply open the generated .eml file, read it, and if you notice a problem, type “2” or “3” to enter your comments and automatically submit a suggestion that you can discuss on https://github.com/dogulSmile/BRAssistant/issues .

```bash
How was this review ? (empty to skip) 
    [1] Perfect
    [2] Good, but missed something
    [3] Hallucination / Bad rule applied : 2
```
If you find the answer correct, just press 'enter' to continue.

To analyze another patch, you can simply enter again another url/path of a patch, and another .eml file will be created.

## 7. Data update

To update the database of the RAG, there is multiple functions to retrieve and format the patches and the documentation.

### Documentation retrieval

`data_construction/documentation_scrapper.py`
This script retrieve Buildroot's documentation and synthesizes it.
It rewrites the content of 'ressources/The_Buildroot_user_manual.html'
```bash
python3 ./data_construction/documentation_scrapper.py
```
### Patches retrieval
`data_construction/patch_scrapper.py`
This script retrieve precedent patches from Patchwork with a specified status.
You can't directly send this list to the DB, please format it with patch_formatter.py before.
```bash
python3 ./data_construction/patch_scrapper.py <output_file_path>
#example : python3 ./data_construction/patch_scrapper.py output/patches.json
```
### Patches formatter
`data_construction/patch_formatter.py`
This script uses AI to format previous patches by summarizing the issue and the solution found by the maintainer, in order to reduce patch size for future vector searches.
```bash
python3 ./data_construction/patch_formatter.py <input_file_path> <output_file_path>
#example : python3 ./data_construction/patch_formatter.py output/patches.json
#default output path is ressources/buildroot_lessons.jsonl
```

Reminder: to push new patches to the database, use `python3 elastic_functions/vectorializer.py -p ressources/buildroot_lessons.jsonl`

## 8. How to choose the AI Model

Currently, there are a few different models supported, and your choice will produce varied results.
There are two types of models here: **"Reasoning"** models and **"Routing"** (Lite) models.
* **Reasoning models** will have slower answer times but provide more in-depth suggestions.
* **Routing models** can answer much faster, but are far less pertinent on complex tasks (they are ideal for extracting manual sections to provide context).

To choose your model, edit the .env file, add your key and enter the model's vairant name.
You cant choose a different model for routing and patch review, it's highly recommended btw.

Here are the pros and cons for each of them to help you choose:

### Reasoning Agents (Code Review)

**`gemini-3.5-flash` (Google)** 
* **Pros:** Gives the most precise answers. Less prone to hallucinations.
* **Cons:** Slowest answers on the free plan and "Best-effort" service; retries might be needed during high demand periods. Limited to 20 requests per day on the free plan.

**`deepseek/deepseek-v4-pro` (or openrouter/owl-alpha) (OpenRouter)** <-- recommended
* **Pros:** Totally free API aggregator. Allows using large context windows (64k+ tokens) avoiding the strict limits of GitHub Models and support multiple models.
* **Cons:** "Deepseek V4 free plan is not always available. Reliability and answer times highly depend on the underlying free providers' current load, and can give less detailed answers compared to gemini.

**`gpt-4o` (via GitHub Models)**
* **Pros:** Solid and detailed answers in general. Few hallucinations. Highly available with fast answer times.
* **Cons:** Input context is strictly limited to 8k tokens (cannot be used on more complex patches with large RAG contexts).

**`Meta-Llama-3.1-405B-Instruct` (via GitHub Models)**
* **Pros:** Detailed answers in general and fast answer times.
* **Cons:** More prone to hallucinations compared to GPT/Gemini. Input context limited to 8k tokens.

**`command-a-plus-05-2026` (Cohere)**
* **Pros:** Canadian open-source project. Good answer times and high availability.
* **Cons:** Lowest capacity for complex reasoning or using "expert intuition". Tends to provide the lowest number of suggestions in its answers.



### Routing Agents (Context Provider)

**`llama-3.3-70b-versatile` (Groq)**
* **Pros:** Very high speed (LPU hardware). Solid choice for fast JSON routing.
* **Cons:** Extremely strict Tokens-Per-Minute (TPM) limits on the free tier (do not use for the Reasoning Agent).

**`gpt-4o-mini` (GitHub Models)**
* **Pros:** Blazing fast answer time and excellent at enforcing JSON structures.
* **Cons:** Subject to API rate limits (10-15 requests/min) on free plans.

**`command-r7b-12-2024` (Cohere)**
* **Pros:** Canadian open-source project. Good answer times and high availability.
* **Cons:** Lower capacity for complex reasoning.

**`gemini-3.1-flash-lite` (Google AI Studio)**
* **Pros:** Fast answer time when available.
* **Cons:** Subject to downtime during high demand on free plans.

### Miscellaneous (non-free alternatives)

There is of course additional models available that would be interesting for this project but would need a financial investment.
Even a very low budget can avoid strict rate limits, timeouts and unlocks the true potential of BRAssistant.

Here are some possibilities:

*Cost estimation baseline on 25/06/2026: A complex patch review with RAG injection averages **20,000 tokens** (19k input context + 1k output generation). API costs are subject to changes.*

**`deepseek-v4-pro (thinking mode)` (Official DeepSeek API)**
* **Pros:** Absolute top-tier coding and reasoning capabilities, matching or beating GPT-4o. Massive 128k context window. Extremely aggressive pricing. 
* **Cons:** Requires topping up a prepaid balance on their platform, and made in China.
* **Estimated Price:** **~$0.009 per review** (Less than a cent!). https://api-docs.deepseek.com/quick_start/pricing

**`anthropic.claude-opus-4-8` (Anthropic API)**
* **Pros:** Widely considered the absolute undisputed king of code review and complex instruction following. Almost zero hallucinations. 200k context window.
* **Cons:** Pricier than DeepSeek, though still cheap for a single review.
* **Estimated Price:** **~$0.06 per review** (6 cents). https://platform.claude.com/docs/en/about-claude/pricing

**`gpt-4o` (Official OpenAI API)**
* **Pros:** The industry standard. Extremely fast and reliable 128k context window without the GitHub Models free tier limitations.
* **Cons:** Currently the most expensive.
* **Estimated Price:** **~$0.0625 per review** (6.25 cents). https://openai.com/api/pricing/

**`grok-4.3 (medium reasoning_effort)` (Groq)**
* **Pros:** 150$/month free tokens, with a mean request around 20k tokens, it would be 5k free requests/month (respect if you ever do 5k reviews). (see https://grok-api.apidog.io/free-credits-934025m0)
* **Cons:** Need a 5$ initial investment, eligibility conditions, and is owned by Elon Musk.
* **Estimated Price:** **~$0.025 per review** (2.5 cents). https://docs.x.ai/developers/models
