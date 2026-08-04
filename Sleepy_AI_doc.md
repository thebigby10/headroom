**Title:** Sleepy AI

**Source:** [https://www.sleepyai.org/docs](https://www.sleepyai.org/docs)

---

# Page Structure Map
```text
Sleepy AI
├── Overview
├── Authentication
├── Base URL
├── Models
│   └── GET /api/v1/models
├── Chat Completions
│   ├── POST /api/v1/chat/completions
│   └── Parameters
├── Response Format
├── Usage & Rate Limits
│   └── Rate Limits
├── Context Caching
├── Error Codes
└── Client SDKs
    ├── Python (openai)
    └── Node.js (openai)
```

---

Integrate Sleepy AI into your applications with the OpenAI-compatible API.

## Overview

Sleepy provides an OpenAI-compatible API for AI completions. You can use any OpenAI client library (Python, Node.js, curl, etc.) by simply changing the base URL and API key.

All requests go through our proxy which handles authentication, rate limiting, usage tracking, and routing to the appropriate AI provider.

## Authentication

Authenticate using a Bearer token in the `Authorization` header:

```
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Generate API keys from the dashboard. Each key is tied to your account and plan tier.

## Base URL

```
https://www.sleepyai.org/api/v1
```

All endpoints are prefixed with this base URL. For example, to list models:

```
curl https://www.sleepyai.org/api/v1/models \
  -H "Authorization: Bearer sk-..."
```

## Models

List available models and their pricing:

#### GET /api/v1/models

Returns a list of active models with pricing, context window, and capabilities.

```
curl https://www.sleepyai.org/api/v1/models \
  -H "Authorization: Bearer sk-..."
```

Each model includes `inputPrice`, `outputPrice`, and `cacheReadPrice` per 1M tokens.

## Chat Completions

Create a chat completion. Fully compatible with the OpenAI Chat Completions API format.

#### POST /api/v1/chat/completions

```
curl https://www.sleepyai.org/api/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true,
    "max_tokens": 1024
  }'
```

#### Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| model | string | Model ID from the models list |
| messages | array | Array of message objects (role + content) |
| stream | boolean | Enable SSE streaming (default: true) |
| max\_tokens | integer | Maximum tokens in the response |
| temperature | number | Sampling temperature (0–2, default: 1) |

## Response Format

Streaming responses use Server-Sent Events (SSE). Each chunk follows the OpenAI format:

```
data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"},"index":0}]}

data: [DONE]
```

Non-streaming responses return the complete message object. Usage data (including cached tokens) is included in the final response.

## Usage & Rate Limits

Usage is tracked per request and displayed in your dashboard. The proxy records prompt tokens, completion tokens, cached tokens, and cost.

#### Rate Limits

-   Requests per minute (RPM) — based on your plan
-   Spending limits per time window (5h, 24h, weekly, monthly)
-   Monthly allowance resets every 30 days
-   Extra credits can be purchased if you exceed your plan allowance

## Context Caching

The proxy supports context caching to reduce costs on repeated prefix content. When enabled, cached portions of the prompt are billed at a lower `cacheReadPrice`.

Cache hit rate and savings are displayed in the usage dashboard. The cache status is reported transparently — no extra configuration needed.

## Error Codes

| Status | Code | Meaning |
| --- | --- | --- |
| 401 | unauthorized | Invalid or missing API key |
| 403 | forbidden | Model disabled or access denied |
| 429 | rate\_limit | Rate or spending limit exceeded |
| 502 | proxy\_error | Upstream provider error |
| 503 | model\_unavailable | Model temporarily disabled |

## Client SDKs

Use any OpenAI-compatible client by pointing it at our base URL:

#### Python (openai)

```
from openai import OpenAI

client = OpenAI(
    base_url="https://www.sleepyai.org/api/v1",
    api_key="sk-..."
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

#### Node.js (openai)

```
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://www.sleepyai.org/api/v1",
  apiKey: "sk-...",
});

const response = await client.chat.completions.create({
  model: "gpt-4",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);
```