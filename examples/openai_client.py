"""Run against a separately started gateway; requires the dev extra."""

import os

from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1", api_key=os.getenv("MEDINFER_API_KEY", "local-unused")
)
model = client.models.list().data[0].id
stream = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Explain what unknown culture means."}],
    max_tokens=512,
    stream=True,
    stream_options={"include_usage": True},
)
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
    if chunk.usage:
        print("\n", chunk.usage)
