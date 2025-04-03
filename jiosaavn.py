import requests
import endpoints
import helper
import json
from traceback import print_exc
import re


def search_for_song(query, lyrics, songdata, limit=50, timeout=3):
    """
    Parse JioSaavn website search results with improved error handling for API use
    """
    import requests
    import json
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Initialize empty result
    all_songs = []
    
    try:
        # Handle direct URLs
        if query and isinstance(query, str) and query.startswith('http') and 'saavn.com' in query:
            id = get_song_id(query)
            try:
                song_data = get_song(id, lyrics)
                if song_data:
                    return [song_data]
                return []
            except Exception as e:
                print(f"Error getting song by ID: {e}")
                return []
        
        # Define request headers once
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.jiosaavn.com/',
        }
        
        # Ensure query is valid
        if not query or not isinstance(query, str) or len(query.strip()) == 0:
            print("Invalid or empty query")
            return []
            
        # Format query for URL safely
        from urllib.parse import quote
        query_encoded = quote(query.strip())
        
        # Step 1: Try the direct API with proper error handling and timeouts
        search_urls = [
            f"https://www.jiosaavn.com/api.php?__call=search.getResults&_format=json&_marker=0&cc=in&q={query_encoded}&n={limit}"
           
        ]
        
        for url in search_urls:
            if len(all_songs) >= limit:
                break
                
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    continue
                    
                response_text = response.text.encode().decode('unicode-escape')
                response_json = json.loads(response_text)
                
                # Extract songs from different possible response formats
                song_data = None
                if 'results' in response_json:
                    song_data = response_json['results']
                elif 'songs' in response_json and 'data' in response_json['songs']:
                    song_data = response_json['songs']['data']
                
                if song_data and isinstance(song_data, list):
                    # Add songs, avoiding duplicates
                    existing_ids = {song.get('id') for song in all_songs if isinstance(song, dict) and 'id' in song}
                    for song in song_data:
                        if isinstance(song, dict) and 'id' in song and song['id'] not in existing_ids:
                            all_songs.append(song)
                            existing_ids.add(song['id'])
            except requests.exceptions.Timeout:
                print(f"Timeout on URL: {url}")
                continue
            except Exception as e:
                print(f"Error on URL {url}: {e}")
                continue
        
        # Step 2: If we don't have enough results, try web scraping as fallback
        if len(all_songs) < min(5, limit):
            try:
                import re
                from bs4 import BeautifulSoup
                
                formatted_query = query.replace(' ', '+')
                search_url = f"https://www.jiosaavn.com/search/{formatted_query}/songs"
                
                scrape_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                
                response = requests.get(search_url, headers=scrape_headers, timeout=timeout)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    script_tags = soup.find_all('script')
                    for script in script_tags:
                        if script.string and 'window.__INITIAL_DATA__' in script.string:
                            json_str = re.search(r'window\.__INITIAL_DATA__\s*=\s*({.*?});', script.string, re.DOTALL)
                            if json_str:
                                try:
                                    json_data = json.loads(json_str.group(1))
                                    if 'songs' in json_data and 'data' in json_data['songs']:
                                        # Add these songs, respecting the existing_ids set
                                        existing_ids = {song.get('id') for song in all_songs if isinstance(song, dict) and 'id' in song}
                                        for song in json_data['songs']['data']:
                                            if isinstance(song, dict) and 'id' in song and song['id'] not in existing_ids:
                                                all_songs.append(song)
                                                existing_ids.add(song['id'])
                                        break
                                except:
                                    continue
            except requests.exceptions.Timeout:
                print("Scraping fallback timed out")
            except Exception as e:
                print(f"Scraping error: {e}")
        
        # Limit results and ensure we have valid data
        all_songs = all_songs[:limit] if all_songs else []
        
        # If we don't need song data, return what we have
        if not songdata:
            return all_songs
        
        # No need to process further if there are no songs
        if not all_songs:
            return []
        
        # Step 3: Get full song data if requested
        songs_with_data = []
        
        def fetch_song_data(song):
            try:
                if not isinstance(song, dict) or 'id' not in song:
                    return None
                    
                id = song['id']
                song_data = get_song(id, lyrics)
                return song_data if song_data else None
            except Exception as e:
                print(f"Error fetching song {song.get('id', 'unknown')}: {e}")
                return None
        
        # CRITICAL FIX: Ensure max_workers is always at least 1
        max_workers = max(1, min(10, len(all_songs)))
        
        # Use ThreadPoolExecutor to fetch song data in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_song = {executor.submit(fetch_song_data, song): song for song in all_songs}
            for future in as_completed(future_to_song):
                result = future.result()
                if result:
                    songs_with_data.append(result)
        
        return songs_with_data
        
    except Exception as e:
        # Catch-all exception handler to prevent API crashes
        print(f"Unexpected error in search_for_song: {e}")
        return []

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
