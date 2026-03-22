import tvdb_v4_official
import datetime
import smtplib, ssl
import time
import os
import json
import urllib.request
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from email.message import EmailMessage


load_dotenv()

THE_TVDB_API_KEY = os.getenv('THE_TVDB_API_KEY')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_USER = os.getenv('SMTP_USER')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_SSL_PORT = 465
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
SERIES_FETCHER_URL = os.getenv('SERIES_FETCHER_URL', 'http://localhost:8090')


def send_telegram(text):
    """Send a message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            pass
    except Exception as e:
        print(f"Telegram send failed: {e}")


def trigger_search(series_name, series_year, season, episodes):
    """Trigger a search on series-fetcher."""
    url = f"{SERIES_FETCHER_URL}/search"
    payload = json.dumps({
        "series_name": series_name,
        "series_year": series_year,
        "season": season,
        "episodes": episodes,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.load(resp)
            print(f"Search triggered: {result}")
            return result
    except Exception as e:
        print(f"Series-fetcher search failed: {e}")
        return None

environment = Environment(loader=FileSystemLoader('./'))
template = environment.get_template('email_template.html')

context = ssl.create_default_context()

tvdb = tvdb_v4_official.TVDB(THE_TVDB_API_KEY)

try:
    favorites = tvdb.get_user_favorites()['series']
except Exception as e:
     print(f"Couldn't retrieve Favorites ({e}), retrying in 5 minutes")
     time.sleep(300)
     favorites = tvdb.get_user_favorites()['series']
     
airs_next = []
series_details = {}
for series in favorites:
    try:
        series_details[series] = tvdb.get_series_extended(id=series)
    except:
         time.sleep(300)
         series_details[series] = tvdb.get_series_extended(id=series)
    print(f'retrieving details for {series_details[series]["name"]} , Series ID: {series}')

    try:
        details = tvdb.get_series_nextAired(id=series)
    except:
         time.sleep(500)
         details = tvdb.get_series_nextAired(id=series)
    if details['nextAired'] != '':
        nextAired = datetime.date.fromisoformat(details['nextAired'])
        today = datetime.date.today()
        if today == nextAired:
            print(f'Today ({today.strftime("%d/%m/%y")}) airs: {series_details[series]["name"]}')
            airs_next.append(series)
        else:
             print(f'No new episode airs today for {series_details[series]["name"]}')
    else:
         print(f'No new episode scheduled for {series_details[series]["name"]}')

for serie in airs_next:
    try:
        episodes = tvdb.get_series_episodes(id=serie)
    except:
         time.sleep(300)
         episodes = tvdb.get_series_episodes(id=serie)
    new_episodes_list = []
    new_episodes_name = {}
    for episode in episodes.get('episodes',[]):
        if episode['aired'] != None:
            if datetime.date.fromisoformat(episode['aired']) == today:
                    season_no = episode['seasonNumber']
                    new_episodes_list.append(episode['number'])
                    new_episodes_name[f'{episode["number"]}'] = episode['name']
    episode_date = today.strftime("%A, %d. %B")
    try:
        artwork_url = series_details[serie]['artworks'][0]['image']
    except:
        artwork_url = ''
    series_name = series_details[serie]['name']
    series_url = 'https://thetvdb.com/series/' + series_details[serie]['slug']
    original_network = series_details[series].get('originalNetwork','').get('name','Unknown Orig Network')
    latest_network = series_details[series].get('latestNetwork', original_network).get('name', original_network)

    if len(new_episodes_list) > 1:
            episode_name = ''
            episode_no = f'{new_episodes_list[0]}-{new_episodes_list[len(new_episodes_list)-1]}'
            for index, episode in enumerate(new_episodes_list):
                episode_name += new_episodes_name[f'{episode}']
                if not index == len(new_episodes_list) -1:
                    episode_name += ', '
    else:
        episode_no = new_episodes_list[0]
        episode_name = new_episodes_name[f'{episode_no}']
    email_content = template.render(
        EPISODE_NAME=episode_name,
        EPISODE_NO=episode_no,
        SEASON_NO=season_no,
        SERIES_NAME=series_name,
        RELEASE_DATE=episode_date,
        SERIES_POSTER_URL=artwork_url,
        SERIES_URL=series_url,
        NETWORK=latest_network
    )
    msg = EmailMessage()
    msg['Subject'] = f'New Episode of {series_name} - Season {season_no}, Episode {episode_no} on {episode_date}'
    msg['From'] = f'Series Reminder Bot <{SMTP_USER}>'
    msg['to'] = RECEIVER_EMAIL
    msg.set_content(email_content, subtype='html')
    print(f'Sending email about new episodes for "{series_details[serie]["name"]}" - Season {season_no} Episode {episode_no}')
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_SSL_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    # Send Telegram notification
    tg_text = (
        f"<b>New Episode</b>: {series_name}\n"
        f"Season {season_no}, Episode {episode_no}\n"
        f"{episode_name}\n"
        f"{episode_date} on {latest_network}"
    )
    send_telegram(tg_text)

    # Trigger series-fetcher search
    series_year = series_details[serie].get('year')
    trigger_search(series_name, series_year, season_no, new_episodes_list)