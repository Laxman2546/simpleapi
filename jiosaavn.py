import requests
import endpoints
import helper
import json
from traceback import print_exc
import re


def search_for_song(query, lyrics, songdata, limit=50):
    """
    Parse JioSaavn website search results to get more comprehensive results
    """
    if query.startswith('http') and 'saavn.com' in query:
        id = get_song_id(query)
        return get_song(id, lyrics)
    
    # First try the direct search API
    try:
        # Try different API endpoints that might return more results
        search_urls = [
            f"https://www.jiosaavn.com/api.php?__call=search.getResults&_format=json&_marker=0&cc=in&q={query}&n={limit}",
            f"https://www.jiosaavn.com/api.php?__call=search.getAll&_format=json&_marker=0&cc=in&q={query}&n={limit}"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.jiosaavn.com/',
        }
        
        all_songs = []
        
        for url in search_urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:
                    continue
                    
                response_text = response.text.encode().decode('unicode-escape')
                response_json = json.loads(response_text)
                
                # Look for songs in different possible response formats
                song_data = None
                if 'results' in response_json:
                    song_data = response_json['results']
                elif 'songs' in response_json and 'data' in response_json['songs']:
                    song_data = response_json['songs']['data']
                
                if song_data:
                    # Add songs, avoiding duplicates
                    existing_ids = {song.get('id') for song in all_songs if 'id' in song}
                    for song in song_data:
                        if 'id' in song and song['id'] not in existing_ids:
                            all_songs.append(song)
                            existing_ids.add(song['id'])
                    
                    if len(all_songs) >= limit:
                        break
            except:
                continue
        
        # If we found enough songs from the APIs, use them
        if len(all_songs) >= min(5, limit):
            all_songs = all_songs[:limit]
            
            if not songdata:
                return all_songs
            
            # Get full song data
            songs_with_data = []
            for song in all_songs:
                try:
                    id = song['id']
                    song_data = get_song(id, lyrics)
                    if song_data:
                        songs_with_data.append(song_data)
                except:
                    continue
            
            return songs_with_data
    except:
        pass
    
    # If API methods failed, try scraping the website as a fallback
    try:
        import re
        from bs4 import BeautifulSoup
        
        # Format query for URL
        formatted_query = query.replace(' ', '+')
        search_url = f"https://www.jiosaavn.com/search/{formatted_query}/songs"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        
        # Parse the HTML to find the embedded JSON data
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # JioSaavn typically embeds song data in a script tag
        script_tags = soup.find_all('script')
        song_data = []
        
        for script in script_tags:
            if script.string and 'window.__INITIAL_DATA__' in script.string:
                # Extract the JSON data
                json_str = re.search(r'window\.__INITIAL_DATA__\s*=\s*({.*?});', script.string, re.DOTALL)
                if json_str:
                    try:
                        json_data = json.loads(json_str.group(1))
                        
                        # Navigate through the JSON structure to find songs
                        if 'songs' in json_data and 'data' in json_data['songs']:
                            song_data = json_data['songs']['data']
                            break
                    except:
                        continue
        
        # Process the extracted song data
        all_songs = song_data[:limit]
        
        if not songdata:
            return all_songs
        
        # Get full song data
        songs_with_data = []
        for song in all_songs:
            try:
                id = song['id']
                song_data = get_song(id, lyrics)
                if song_data:
                    songs_with_data.append(song_data)
            except:
                continue
        
        return songs_with_data
    except Exception as e:
        print(f"Search error: {e}")
        return []

# The rest of your code remains unchanged...

def get_song(id, lyrics):
    try:
        song_details_base_url = endpoints.song_details_base_url+id
        song_response = requests.get(
            song_details_base_url).text.encode().decode('unicode-escape')
        song_response = json.loads(song_response)
        song_data = helper.format_song(song_response[id], lyrics)
        if song_data:
            return song_data
    except:
        return None


def get_song_id(url):
    res = requests.get(url, data=[('bitrate', '320')])
    try:
        return(res.text.split('"pid":"'))[1].split('","')[0]
    except IndexError:
        return res.text.split('"song":{"type":"')[1].split('","image":')[0].split('"id":"')[-1]


def get_album(album_id, lyrics):
    songs_json = []
    try:
        response = requests.get(endpoints.album_details_base_url+album_id)
        if response.status_code == 200:
            songs_json = response.text.encode().decode('unicode-escape')
            songs_json = json.loads(songs_json)
            return helper.format_album(songs_json, lyrics)
    except Exception as e:
        print(e)
        return None


def get_album_id(input_url):
    res = requests.get(input_url)
    try:
        return res.text.split('"album_id":"')[1].split('"')[0]
    except IndexError:
        return res.text.split('"page_id","')[1].split('","')[0]


def get_playlist(listId, lyrics):
    try:
        response = requests.get(endpoints.playlist_details_base_url+listId)
        if response.status_code == 200:
            songs_json = response.text.encode().decode('unicode-escape')
            songs_json = json.loads(songs_json)
            return helper.format_playlist(songs_json, lyrics)
        return None
    except Exception:
        print_exc()
        return None


def get_playlist_id(input_url):
    res = requests.get(input_url).text
    try:
        return res.split('"type":"playlist","id":"')[1].split('"')[0]
    except IndexError:
        return res.split('"page_id","')[1].split('","')[0]


def get_lyrics(id):
    url = endpoints.lyrics_base_url+id
    lyrics_json = requests.get(url).text
    lyrics_text = json.loads(lyrics_json)
    return lyrics_text['lyrics']
