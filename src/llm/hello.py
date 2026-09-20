import os
from dotenv import load_dotenv
from openai import OpenAI

# Load settings from .env
load_dotenv()

# Create the client
client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"]
)

# Ask the model for one response
res = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly the word: ready"
        }
    ],
)

# Print the model's response
print(res.choices[0].message.content)