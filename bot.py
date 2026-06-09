import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials

# Environment
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
TWITCH_CHANNEL_LOGIN = os.environ["TWITCH_CHANNEL_LOGIN"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]

TWITCH_URL = f"https://twitch.tv/{TWITCH_CHANNEL_LOGIN}"

# Google Sheets setup
creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
scopes = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet('state')
try:
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet('state')
except gspread.WorksheetNotFound:
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).add_worksheet(title='state', rows=10, cols=2)


def load_state():
    data = sheet.get_all_values()
    if len(data) < 2:
        sheet.update('A1:B1', [['was_live', 'message_id']])
        sheet.update('A2:B2', [['false', '']])
        data = sheet.get_all_values()
    was_live = data[1][0].lower() == 'true'
    message_id = int(data[1][1]) if data[1][1] else None
    return {"was_live": was_live, "message_id": message_id}


def save_state(state):
    sheet.update('A2:B2', [[str(state["was_live"]).lower(), state.get("message_id") or ""]])


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
                "inline_keyboard": [[{"text": "Смотреть стрим", "url": TWITCH_URL}]]
            },
        },
        timeout=20,
    )
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


def main():
    state = load_state()
    live_now = is_live()
    was_live = state.get("was_live", False)

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
        print("Статус без изменений.")
        save_state(state)


if __name__ == "__main__":
    main()
