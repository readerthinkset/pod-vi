"""Set the Velocity Vietnamese Podcast YouTube channel description (About section)."""
import os, json
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

CHANNEL_DESCRIPTION = '🇻🇳 Velocity Vietnamese Podcast - Learn Vietnamese naturally\\n\\nOfficial Website: https://velocityvietnamese.com/\\nFree Study Guides: https://velocityvietnamese.com/blog/\\n\\nDaily bilingual Vietnamese podcast with English translation. Simple A2-level conversations between Minh and Linh. Every Vietnamese line includes English translation.\\n\\nWHAT YOU WILL GET:\\n- Daily bilingual conversations (Vietnamese + English)\\n- Natural pronunciation from native speakers\\n- Practical vocabulary for everyday life\\n- Free companion guides at velocityvietnamese.com\\n\\nHow to use this podcast:\\n1. Listen to the Vietnamese, try to understand\\n2. Check the English translation\\n3. Repeat the phrases out loud\\n\\nSubscribe for daily lessons.\\n\\nNew episodes every day!\\n\\n#LearnVietnamese #VietnamesePodcast #Bilingual #LanguageLearning #VelocityVietnamese'


def _get_creds():
    cid = os.getenv("YT_CLIENT_ID")
    csecret = os.getenv("YT_CLIENT_SECRET")
    refresh = os.getenv("YT_REFRESH_TOKEN")
    if cid and csecret and refresh:
        return Credentials(None, refresh_token=refresh,
                           token_uri="https://oauth2.googleapis.com/token",
                           client_id=cid, client_secret=csecret)
    tok_file = Path(__file__).parent / "token.json"
    candidates = [
        tok_file,
        Path('C:/Users/kreg9/Downloads/kreggscode/open code/bots/youtube refresh tokens bot/token_Velocity Vietnamese podcast.json'),
    ]
    for c in candidates:
        if c.exists():
            tok = json.load(open(c, encoding='utf-8'))
            return Credentials(None, refresh_token=tok['refresh_token'],
                               token_uri="https://oauth2.googleapis.com/token",
                               client_id=tok['client_id'], client_secret=tok['client_secret'])
    raise ValueError("No YouTube credentials found")


def main():
    creds = _get_creds()
    creds.refresh(Request())
    service = build("youtube", "v3", credentials=creds)
    channels = service.channels().list(part="brandingSettings", mine=True).execute()
    channel_id = channels["items"][0]["id"]
    branding = dict(channels["items"][0]["brandingSettings"])
    branding.setdefault("channel", {})
    branding["channel"]["description"] = CHANNEL_DESCRIPTION
    body = {"id": channel_id, "brandingSettings": branding}
    resp = service.channels().update(part="brandingSettings", body=body).execute()
    new_desc = resp["brandingSettings"]["channel"].get("description", "")
    print("Channel:", channel_id)
    print("Description set to", len(new_desc), "chars")


if __name__ == "__main__":
    main()
