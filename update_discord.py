import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])

DISCORD_API = "https://discord.com/api/v10"
DATA_URL = "https://raw.githubusercontent.com/RaidTheory/arcraiders-data/main/map-events/map-events.json"

PACIFIC_TZ = ZoneInfo("America/Vancouver")
CENTRAL_TZ = ZoneInfo("America/Chicago")

MAP_COLORS = {
    "the-spaceport": 0x3498db,
    "dam-battleground": 0x2ecc71,
    "buried-city": 0xe67e22,
    "blue-gate": 0x1abc9c,
    "stella-montis": 0x9b59b6,
}


def http_json(url, method="GET", data=None, auth=False):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bot {DISCORD_TOKEN}"

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def discord_get(path):
    return http_json(f"{DISCORD_API}{path}", auth=True)


def discord_post(path, payload):
    return http_json(f"{DISCORD_API}{path}", method="POST", data=payload, auth=True)


def discord_patch(path, payload):
    return http_json(f"{DISCORD_API}{path}", method="PATCH", data=payload, auth=True)


def discord_put(path):
    return http_json(f"{DISCORD_API}{path}", method="PUT", auth=True)


def load_data():
    with urllib.request.urlopen(DATA_URL, timeout=20) as resp:
        return json.loads(resp.read().decode())


def format_duration(delta):
    total_seconds = max(0, int(delta.total_seconds()))
    h, rem = divmod(total_seconds, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m}m"


def format_time(dt):
    p = dt.astimezone(PACIFIC_TZ)
    c = dt.astimezone(CENTRAL_TZ)
    return f"{p.strftime('%H:%M')} {p.tzname()} | {c.strftime('%H:%M')} {c.tzname()}"


def get_bot_user_id():
    return discord_get("/users/@me")["id"]


def get_pinned_bot_message(bot_id):
    pins = discord_get(f"/channels/{CHANNEL_ID}/pins")
    for msg in pins:
        if msg["author"]["id"] == bot_id:
            return msg
    return None


def build_embeds(data):
    now = datetime.now(timezone.utc)

    # ===== HEADER (THIS IS YOUR NEW PART) =====
    pacific_now = now.astimezone(PACIFIC_TZ)
    central_now = now.astimezone(CENTRAL_TZ)

    header_text = (
        f"Last updated: {pacific_now.strftime('%H:%M')} {pacific_now.tzname()} | "
        f"{central_now.strftime('%H:%M')} {central_now.tzname()}\n"
        f"Updates every 5 minutes."
    )

    embeds = [
        {
            "description": header_text,
            "color": 0x2F3136
        }
    ]
    # =========================================

    for map_key, map_data in data.items():
        schedule = sorted((int(h), e) for h, e in map_data["schedule"].items())

        current_lines = []
        next_lines = []

        for hour, event in schedule:
            start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hour - now.hour)
            if start < now:
                start += timedelta(days=1)

            end = start + timedelta(hours=1)

            if start <= now < end:
                remaining = end - now
                current_lines.append(f"{event} (ends in {format_duration(remaining)})")
            elif start > now and len(next_lines) < 3:
                delta = start - now
                next_lines.append(
                    f"{event} at {format_time(start)} (in {format_duration(delta)})"
                )

        embed = {
            "title": map_key.replace("-", " ").title(),
            "color": MAP_COLORS.get(map_key, 0x95A5A6),
            "fields": [
                {
                    "name": "Current Events",
                    "value": "\n".join(current_lines) if current_lines else "None",
                    "inline": False,
                },
                {
                    "name": "Next Three Events",
                    "value": "\n".join(next_lines) if next_lines else "None",
                    "inline": False,
                },
            ],
        }

        embeds.append(embed)

    return embeds


def main():
    data = load_data()

    bot_id = get_bot_user_id()
    existing = get_pinned_bot_message(bot_id)

    embeds = build_embeds(data)
    payload = {"embeds": embeds}

    if existing:
        discord_patch(f"/channels/{CHANNEL_ID}/messages/{existing['id']}", payload)
    else:
        msg = discord_post(f"/channels/{CHANNEL_ID}/messages", payload)
        discord_put(f"/channels/{CHANNEL_ID}/pins/{msg['id']}")


if __name__ == "__main__":
    main()