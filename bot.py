import os
import json
import requests

STATE_FILE = "state.json"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
TWITCH_CHANNEL_LOGIN = os.environ["TWITCH_CHANNEL_LOGIN"]

TWITCH_URL = f"https://twitch.tv/{TWITCH_CHANNEL_LOGIN}"


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"was_live": False, "message_id": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


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
    text = f"🔴 LIVE\nЗаходи на стрим:\n{TWITCH_URL}"

    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": text,
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "Смотреть стрим", "url": TWITCH_URL}]
                ]
            },
        },
        timeout=20,
    )
    r.raise_for_status()

    return r.json()["result"]["message_id"]


def delete_live_message(message_id):
    if not message_id:
        return

    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage",
        json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "message_id": message_id,
        },
        timeout=20,
    )

    print(r.text)


def main():
    state = load_state()
    live_now = is_live()
    was_live = state.get("was_live", False)

    print(f"live_now={live_now}")
    print(f"was_live={was_live}")

    if live_now and not was_live:
        message_id = send_live_message()

        state["was_live"] = True
        state["message_id"] = message_id
        save_state(state)

        print("Стрим онлайн. Сообщение отправлено.")

    elif not live_now and was_live:
        delete_live_message(state.get("message_id"))

        state["was_live"] = False
        state["message_id"] = None
        save_state(state)

        print("Стрим оффлайн. Сообщение удалено.")

    else:
        save_state(state)
        print("Статус без изменений.")


if __name__ == "__main__":
    main()
