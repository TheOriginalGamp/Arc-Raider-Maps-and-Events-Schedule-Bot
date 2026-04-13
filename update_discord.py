import os
import urllib.request

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

print("=== DEBUG TOKEN ===")
print("length:", len(DISCORD_TOKEN))
print("dot_count:", DISCORD_TOKEN.count("."))
print("has_whitespace:", any(ch.isspace() for ch in DISCORD_TOKEN))
print("starts_with_bot_prefix:", DISCORD_TOKEN.startswith("Bot "))
print("first_10_chars:", DISCORD_TOKEN[:10])
print("===================")

req = urllib.request.Request(
    "https://discord.com/api/v10/users/@me",
    headers={
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "User-Agent": "ARCEventsBotTest/1.0",
    },
    method="GET",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("status:", resp.status)
        print(resp.read().decode())
except Exception as e:
    print("REQUEST FAILED")
    print(e)