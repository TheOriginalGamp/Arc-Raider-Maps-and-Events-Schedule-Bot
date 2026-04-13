import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]

DATA_URL = "https://raw.githubusercontent.com/RaidTheory/arcraiders-data/refs/heads/main/map-events/map-events.json"
DISCORD_API = "https://discord.com/api/v10"

PACIFIC_TZ = ZoneInfo("America/Vancouver")
CENTRAL_TZ = ZoneInfo("America/Chicago")

MAP_COLORS = {
    "the-spaceport": 0x3498DB,
    "dam-battleground": 0x2ECC71,
    "buried-city": 0xE67E22,
    "blue-gate": 0x1ABC9C,
    "stella-montis": 0x9B59B6,
}


def log(msg: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")


def http_json(url: str, method: str = "GET", data: dict | None = None, auth: bool = False):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bot {DISCORD_TOKEN}"

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def discord_get(path: str):
    return http_json(f"{DISCORD_API}{path}", auth=True)


def discord_post(path: str, payload: dict):
    return http_json(f"{DISCORD_API}{path}", method="POST", data=payload, auth=True)


def discord_patch(path: str, payload: dict):
    return http_json(f"{DISCORD_API}{path}", method="PATCH", data=payload, auth=True)


def discord_put(path: str):
    return http_json(f"{DISCORD_API}{path}", method="PUT", data={}, auth=True)


def load_data() -> dict:
    with urllib.request.urlopen(DATA_URL, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sorted_schedule(schedule_dict: dict) -> list[tuple[int, str]]:
    return sorted((int(hour), event_id) for hour, event_id in schedule_dict.items())


def format_duration(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m"


def format_time(dt: datetime) -> str:
    pacific = dt.astimezone(PACIFIC_TZ)
    central = dt.astimezone(CENTRAL_TZ)
    return f"{pacific.strftime('%H:%M')} {pacific.tzname()} | {central.strftime('%H:%M')} {central.tzname()}"


def get_current(schedule: dict, event_types: dict, now: datetime):
    items = sorted_schedule(schedule)
    if not items:
        return None

    hour = now.hour
    idx = 0
    for i, (h, _) in enumerate(items):
        if h <= hour:
            idx = i
        else:
            break

    _, event_id = items[idx]
    next_idx = (idx + 1) % len(items)
    next_hour, _ = items[next_idx]

    end = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    if next_hour <= hour:
        end += timedelta(days=1)

    name = event_types.get(event_id, {}).get("displayName", event_id)
    return name, end - now


def get_upcoming(schedule: dict, event_types: dict, now: datetime) -> list[tuple[datetime, str]]:
    items = sorted_schedule(schedule)
    upcoming = []

    for d in range(3):
        for h, event_id in items:
            dt = now.replace(hour=h, minute=0, second=0, microsecond=0) + timedelta(days=d)
            if dt > now:
                name = event_types.get(event_id, {}).get("displayName", event_id)
                upcoming.append((dt, name))

    upcoming.sort(key=lambda x: x[0])
    return upcoming


def build_embeds() -> list[dict]:
    data = load_data()
    event_types = data["eventTypes"]
    maps = data["maps"]
    schedules = data["schedule"]
    now = datetime.now(timezone.utc)

    embeds = []

    for map_key, map_info in maps.items():
        map_name = map_info["displayName"]
        map_schedule = schedules.get(map_key, {})

        current_a = get_current(map_schedule.get("major", {}), event_types, now)
        current_b = get_current(map_schedule.get("minor", {}), event_types, now)

        current_lines = []
        seen_current = set()

        for ev in [current_a, current_b]:
            if ev and ev[0] not in seen_current:
                seen_current.add(ev[0])
                current_lines.append(f"• {ev[0]} (ends in {format_duration(ev[1])})")

        upcoming = get_upcoming(map_schedule.get("major", {}), event_types, now)
        upcoming += get_upcoming(map_schedule.get("minor", {}), event_types, now)
        upcoming.sort(key=lambda x: x[0])

        next_lines = []
        seen_next = set()

        for dt, event_name in upcoming:
            dedupe_key = (dt.isoformat(), event_name)
            if dedupe_key not in seen_next:
                seen_next.add(dedupe_key)
                next_lines.append(
                    f"• {event_name} at {format_time(dt)} (in {format_duration(dt - now)})"
                )
            if len(next_lines) >= 3:
                break

        pacific_now = now.astimezone(PACIFIC_TZ)
        central_now = now.astimezone(CENTRAL_TZ)

        embed = {
            "title": map_name,
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
            "footer": {
                "text": f"Last updated {pacific_now.strftime('%H:%M')} {pacific_now.tzname()} | {central_now.strftime('%H:%M')} {central_now.tzname()}"
            },
        }

        embeds.append(embed)

    return embeds


def get_bot_user_id() -> str:
    me = discord_get("/users/@me")
    return me["id"]


def find_existing_pinned_message(bot_user_id: str) -> dict | None:
    pins = discord_get(f"/channels/{CHANNEL_ID}/pins")
    for msg in pins:
        if msg.get("author", {}).get("id") == bot_user_id:
            return msg
    return None


def create_message(embeds: list[dict]) -> dict:
    payload = {"embeds": embeds}
    return discord_post(f"/channels/{CHANNEL_ID}/messages", payload)


def edit_message(message_id: str, embeds: list[dict]) -> dict:
    payload = {"embeds": embeds}
    return discord_patch(f"/channels/{CHANNEL_ID}/messages/{message_id}", payload)


def pin_message(message_id: str) -> None:
    discord_put(f"/channels/{CHANNEL_ID}/pins/{message_id}")


def main():
    log("Building embeds")
    embeds = build_embeds()

    bot_user_id = get_bot_user_id()
    existing = find_existing_pinned_message(bot_user_id)

    if existing:
        message_id = existing["id"]
        log(f"Editing pinned message {message_id}")
        edit_message(message_id, embeds)
    else:
        log("No pinned bot message found, creating one")
        msg = create_message(embeds)
        message_id = msg["id"]
        log(f"Created message {message_id}, pinning")
        pin_message(message_id)

    log("Done")


if __name__ == "__main__":
    main()
