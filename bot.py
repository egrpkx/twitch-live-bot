import os
import json
import requests
import subprocess

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
TWITCH_CHANNEL_LOGIN = os.environ["TWITCH_CHANNEL_LOGIN"]

STATE_FILE = "state.json"
TWITCH_URL = f"https://twitch.tv/{TWITCH_CHANNEL_LOGIN}"


def load_state():
    if not os.path.exists(STATE_FILE):
        state = {"was_live": False, "message_id": None}
        save_state(state)
        return state
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_twitch_token():
    r = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def is_live():
    token = get_twitch_token()
    r = requests.get(
        "https://api.twitch.tv/helix/streams",
        headers={
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        },
        params={"user_login": TWITCH_CHANNEL_LOGIN},
        timeout=20,
    )
    r.raise_for_status()
    return len(r.json().get("data", [])) > 0


def send_live_message():
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": f"🔴 LIVE\nЗаходи на стрим:\n{TWITCH_URL}",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [[{"text": "Смотреть стрим", "url": TWITCH_URL}]]},
    }
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


def delete_live_message(message_id):
    if not message_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage",
        json={"chat_id": TELEGRAM_CHANNEL_ID, "message_id": message_id},
        timeout=20,
    )


def commit_state():
    try:
        subprocess.run(["git", "add", STATE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update state.json"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print("Git commit/push failed:", e)


def main():
    state = load_state()
    live_now = is_live()
    was_live = state["was_live"]

    if live_now and not was_live:
        message_id = send_live_message()
        state["was_live"] = True
        state["message_id"] = message_id
        save_state(state)
        commit_state()
        print("Стрим онлайн. Сообщение отправлено.")

    elif not live_now and was_live:
        delete_live_message(state["message_id"])
        state["was_live"] = False
        state["message_id"] = None
        save_state(state)
        commit_state()
        print("Стрим оффлайн. Сообщение удалено.")

    else:
        print("Статус без изменений.")


if __name__ == "__main__":
    main()
