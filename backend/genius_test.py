import os
import requests
from bs4 import BeautifulSoup

GENIUS_ACCESS_TOKEN = os.getenv('GENIUS_ACCESS_TOKEN')

headers = {
    'Authorization': f'Bearer {GENIUS_ACCESS_TOKEN}'
}

song_title = 'Bohemian Rhapsody'
artist_name = 'Queen'

search_url = f'https://api.genius.com/search?q={song_title} {artist_name}'
search_response = requests.get(search_url, headers=headers)
print(f'Search status code: {search_response.status_code}')
search_data = search_response.json()

hits = search_data.get('response', {}).get('hits', [])
if not hits:
    print('No results found for the song.')
    exit(1)

song_id = hits[0]['result']['id']
print(f'Found song ID: {song_id}')

song_url = f'https://api.genius.com/songs/{song_id}'
song_response = requests.get(song_url, headers=headers)
print(f'Song details status code: {song_response.status_code}')
song_data = song_response.json()

lyrics_url = song_data.get('response', {}).get('song', {}).get('url')
if not lyrics_url:
    print('Could not find lyrics URL for the song.')
    exit(1)

print(f'Lyrics page URL: {lyrics_url}')

page_response = requests.get(lyrics_url)
if page_response.status_code != 200:
    print(f'Failed to fetch lyrics page. Status code: {page_response.status_code}')
    exit(1)

soup = BeautifulSoup(page_response.text, 'html.parser')
lyrics_divs = soup.find_all('div', attrs={'data-lyrics-container': 'true'})
lyrics = '\n'.join([div.get_text(separator='\n').strip() for div in lyrics_divs])

if lyrics:
    print('Lyrics found:')
    print(lyrics)
else:
    print('Could not find lyrics on the page.') 