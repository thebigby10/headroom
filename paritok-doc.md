**Title:** Build with Paritok: The Token-Efficiency Hackathon

**Source:** [https://build-with-paritok.devpost.com/resources](https://build-with-paritok.devpost.com/resources)

---

# Page Structure Map
```text
Build with Paritok: The Token-Efficiency Hackathon
├── Models & Code
├── Attribution
└── Submission Help
```

---

**Getting Started**

This hackathon runs on Paritok's hosted **GPU server** — free for all hackers, faster than a laptop GPU, and it tracks your token and cost savings on a live dashboard. No local model download needed.

Paritok runs as a proxy between your agent and the LLM API: it compresses each request's context, forwards it upstream, and your agent doesn't change — it just points at Paritok.

1\. **Install:**

   pip install "paritok\[proxy\]"

2\. **Get your API key:** sign up on the Paritok website and create an API key from your dashboard.

3\. **Initialize:** run paritok init in your project directory to generate a paritok.yaml. Note: whatever directory you run init in is the directory you run Paritok from afterward — it reads the paritok.yaml in your current working directory.

4\. **Configure the GPU server:** open paritok.yaml, set use\_gpu\_server: true, and paste in your API key.

5\. **Start the proxy** — from the same directory as your paritok.yaml:

   paritok proxy --port 8080 --config-file paritok.yaml

Keep this terminal open — the proxy has to stay running for the whole session. Run your agent from a _separate_ terminal.

6\. **Point your agent at it** — set the base URL in the shell that launches your agent, then start the agent:

   # macOS / Linux
   export ANTHROPIC\_BASE\_URL=http://127.0.0.1:8080   # Claude Code
   export OPENAI\_BASE\_URL=http://127.0.0.1:8080      # Cursor / OpenAI-SDK agents

   # Windows PowerShell
   $env:ANTHROPIC\_BASE\_URL = "http://127.0.0.1:8080"
   $env:OPENAI\_BASE\_URL    = "http://127.0.0.1:8080"

**Check it's working (optional):** curl http://127.0.0.1:8080/stats shows live compression totals, and your savings also appear in real time on your dashboard.

Full details — SDK mode, API key setup, per-model pricing — are in the README. **Hitting a snag while configuring or running Paritok? Ask in the Discord** — the team is on hand throughout the hackathon for setup, integration, and debugging help, and it's where to report bugs.

#### Models & Code

-   Paritok on GitHub
-   Open-source models

#### Attribution

Crediting Paritok with a link in your README is **required.** A simple line works:

Built with \Paritok\.

Or, **optionally**, use a badge:

\!\[Built with Paritok\\](https://github.com/Paritok-official/paritok-4b-v1)

-   Discord — technical support, integration help, and other builders
-   Contact: paritok9@gmail.com

#### Submission Help

-   Full rules & judging criteria: see the **Rules tab** and **Judging Criteria**



Quick start

Point the proxy at the hosted endpoint with your key — it compresses each turn, then forwards to Anthropic / OpenAI.
compress a segment (hosted API)

curl https://www.paritok.com/api/compress \
  -H "Authorization: Bearer $PARITOK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def add(a, b):\n    return a + b",
    "query": "fix the add helper",
    "kind": "file_read"
  }'
# → { "compressed": "…", "gpu_available": … }

run as a compressing proxy

# Route your agent through the Paritok proxy instead of the raw API.
# It compresses each turn, then forwards to Anthropic / OpenAI.
pip install "paritok[proxy]"

# use_gpu_server: true + your key in paritok.yaml (or PARITOK_API_KEY)
export PARITOK_API_KEY="pk_live_…"
paritok up          # starts the proxy — LEAVE THIS TERMINAL RUNNING

# then, in a SEPARATE terminal, point your agent at it:
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080   # Claude Code
export OPENAI_BASE_URL=http://127.0.0.1:8080      # Codex / OpenAI agents
