import os

# ponytail: minimal .env loader — real env always wins, no dotenv dep
try:
    with open(os.path.join(os.getcwd(), ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())
except FileNotFoundError:
    pass
