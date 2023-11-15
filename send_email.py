import tvdb_v4_official
import datetime
import smtplib, ssl
import os
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

environment = Environment(loader=FileSystemLoader('./'))
template = environment.get_template('email_template.html')

context = ssl.create_default_context()

tvdb = tvdb_v4_official.TVDB(THE_TVDB_API_KEY)

favorites = tvdb.get_user_favorites()['series']
airs_next = []
for series in favorites:
    series_details = tvdb.get_series_extended(id=series)
    print(f'retrieving details for {series_details["name"]}')
    details = tvdb.get_series_nextAired(id=series)
    if details['nextAired'] != '':
        nextAired = datetime.date.fromisoformat(details['nextAired'])
        today = datetime.date.today()
        if today == nextAired:
            print(f'Today airs: {series_details["name"]}')
            airs_next.append(series)

for serie in airs_next:
    episodes = tvdb.get_series_episodes(id=serie)
    series_details = tvdb.get_series_extended(id=series)
    new_episodes_list = []
    new_episodes_name = {}
    for episode in episodes.get('episodes',[]):
        if datetime.date.fromisoformat(episode['aired']) == today:
                season_no = episode['seasonNumber']
                new_episodes_list.append(episode['number'])
                new_episodes_name[f'{episode["number"]}'] = episode['name']
    episode_date = today.strftime("%A, %d. %B")
    try:
        artwork_url = series_details['artworks'][0]['image']
    except:
        artwork_url = ''
    series_name = series_details['name']
    series_url = 'https://thetvdb.com/series/' + series_details['slug']
    if len(new_episodes_list) > 1:
            episode_name = ''
            episode_no = f'{new_episodes_list[0]}-{new_episodes_list[len(new_episodes_list)-1]}'
            for index, episode in enumerate(new_episodes_list):
                episode_name += new_episodes_name[f'{episode}']
                if not index == len(new_episodes_list) -1:
                    episode_name += ', '
    else:
        episode_no = episode['number']
        episode_name = episode['name']
    email_content = template.render(
        EPISODE_NAME=episode_name,
        EPISODE_NO=episode_no,
        SEASON_NO=season_no,
        SERIES_NAME=series_name,
        RELEASE_DATE=episode_date,
        SERIES_POSTER_URL=artwork_url,
        SERIES_URL=series_url
    )
    msg = EmailMessage()
    msg['Subject'] = f'New Episode of {series_name} Season {season_no} on {episode_date}'
    msg['From'] = f'Series Reminder Bot <{SMTP_USER}>'
    msg['to'] = RECEIVER_EMAIL
    msg.set_content(email_content, subtype='html')
    print(f'Sending email about new episodes for "{series_details["name"]}"')
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_SSL_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    # DEBUG to test the Mail template
    # with open(f'./email_{series_name}.html', mode="w", encoding="utf-8") as message:
    #     message.write(email_content)