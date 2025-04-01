from flask import Flask, request, jsonify
import json
import requests
import os
from traceback import print_exc
from flask_cors import CORS
import jiosaavn
import random
import re
import base64
from pyDes import des, ECB, PAD_PKCS5
from flask import Flask, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET", 'thankyoutonystark#weloveyou3000')
CORS(app)

# Queue system
queue = {
    'current_index': 0,
    'tracks': [],
    'shuffle': False,
    'repeat': False,
    'related_songs': []
}

@app.route('/')
def home():
    return jsonify({
        "message": "JioSaavn API",
        "endpoints": {
            "/homepage": "Get homepage data",
            "/song?query=<name>": "Search songs",
            "/queue/search?query=<name>": "Search and create queue",
            "/queue/next": "Get next song in queue",
            "/queue/status": "Get queue status"
        }
    })
def clean_jsonp(response_text):
    """Clean JSONP response to extract pure JSON"""
    try:
        # Remove JSONP wrapper and callback function
        cleaned = re.sub(r'^[^{]*', '', response_text)
        cleaned = re.sub(r'[^}]*$', '', cleaned)
        return json.loads(cleaned)
    except Exception as e:
        print(f"Error cleaning JSONP: {e}")
        return None
@app.route('/homepage')
def get_jiosaavn_homepage_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    url = "https://www.jiosaavn.com/api.php?__call=webapi.getBrowseHoverDetails&is_entity_page=false&language=telugu&api_version=4&_format=json&_marker=0"
    

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        else:
            return jsonify({"error": "Failed to fetch homepage data", "status_code": response.status_code}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/homepage/telugu')
def get_telugu_homepage():
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "te-IN,te;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.jiosaavn.com/",
        "Cookie": "L=telugu"
    }
    
    # Use the same endpoint that's working for telugu/content
    url = "https://www.jiosaavn.com/api.php?__call=content.getHomepageData&language=telugu&_format=json&_marker=0"
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                raw_data = response.json()
            except json.JSONDecodeError:
                raw_data = clean_jsonp(response.text)
                if not raw_data:
                    return jsonify({"error": "Failed to parse Telugu homepage data"}), 500
            
            # Process the data into our desired format
            telugu_data = {
                "banners": [],
                "trending_songs": [],
                "new_releases": [],
                "featured_playlists": [],
                "radio_stations": []
            }
            
            # Extract new releases (albums)
            if "new_albums" in raw_data and isinstance(raw_data["new_albums"], list):
                for album in raw_data["new_albums"]:
                    if isinstance(album, dict):
                        artists = []
                        if "Artist" in album and "music" in album["Artist"]:
                            for artist in album["Artist"]["music"]:
                                if isinstance(artist, dict):
                                    artists.append(artist.get("name", ""))
                        
                        artist_name = ", ".join(artists) if artists else ""
                        
                        telugu_data["new_releases"].append({
                            "id": album.get("albumid", ""),
                            "title": album.get("title", ""),
                            "artist": artist_name,
                            "image": album.get("image", "").replace("150x150", "500x500") if album.get("image") else "",
                            "url": f"https://www.jiosaavn.com/album/{album.get('query', '').replace(' ', '-')}/{album.get('albumid', '')}",
                            "language": album.get("language", "telugu")
                        })
            
            # Extract trending playlists if available
            if "top_playlists" in raw_data and isinstance(raw_data["top_playlists"], list):
                for playlist in raw_data["top_playlists"]:
                    if isinstance(playlist, dict):
                        telugu_data["featured_playlists"].append({
                            "id": playlist.get("id", ""),
                            "title": playlist.get("title", playlist.get("listname", "")),
                            "image": playlist.get("image", "").replace("150x150", "500x500") if playlist.get("image") else "",
                            "url": playlist.get("perma_url", "")
                        })
            
            # Extract top songs if available
            if "top_playlists" in raw_data and isinstance(raw_data["top_playlists"], list):
                for playlist in raw_data["top_playlists"]:
                    if isinstance(playlist, dict) and playlist.get("title") == "Weekly Top Songs" and "songs" in playlist:
                        for song in playlist.get("songs", []):
                            if isinstance(song, dict):
                                telugu_data["trending_songs"].append({
                                    "id": song.get("id", ""),
                                    "title": song.get("title", ""),
                                    "artist": song.get("artist", song.get("primary_artists", "")),
                                    "image": song.get("image", "").replace("150x150", "500x500") if song.get("image") else "",
                                    "url": song.get("perma_url", ""),
                                    "language": "telugu"
                                })
                        break
            
            # Get charts if available
            if "charts" in raw_data and isinstance(raw_data["charts"], list):
                for chart in raw_data["charts"]:
                    if isinstance(chart, dict) and "songs" in chart and isinstance(chart["songs"], list):
                        for song in chart["songs"]:
                            if isinstance(song, dict) and song not in telugu_data["trending_songs"]:
                                telugu_data["trending_songs"].append({
                                    "id": song.get("id", ""),
                                    "title": song.get("title", ""),
                                    "artist": song.get("artist", song.get("primary_artists", "")),
                                    "image": song.get("image", "").replace("150x150", "500x500") if song.get("image") else "",
                                    "url": song.get("perma_url", ""),
                                    "language": "telugu"
                                })
            
            # Add featured radio stations
            if "radio_stations" in raw_data and isinstance(raw_data["radio_stations"], list):
                for station in raw_data["radio_stations"]:
                    if isinstance(station, dict):
                        telugu_data["radio_stations"].append({
                            "id": station.get("id", ""),
                            "title": station.get("title", ""),
                            "image": station.get("image", ""),
                            "url": station.get("perma_url", "")
                        })
            
            # Add a more focused way to get Telugu songs
            @app.route('/telugu/top-songs')
            def get_telugu_top_songs():
                headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                    "Accept-Language": "te-IN,te;q=0.9",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.jiosaavn.com/",
                    "Cookie": "L=telugu"
                }
                
                # This URL specifically gets Telugu top songs
                url = "https://www.jiosaavn.com/api.php?__call=content.getCharts&language=telugu&_format=json"
                
                try:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            data = clean_jsonp(response.text)
                        
                        return jsonify(data)
                    else:
                        return jsonify({"error": "Failed to fetch Telugu top songs"}), 500
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
            
            return jsonify(telugu_data)
        else:
            return jsonify({"error": f"Telugu homepage request failed with status code: {response.status_code}"}), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        return jsonify({"error": str(e), "traceback": error_details}), 500

# Alternative approach using a different API endpoint that might work better for Telugu content
@app.route('/telugu/content')
def get_telugu_content():
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "te-IN,te;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.jiosaavn.com/",
        "Cookie": "L=telugu"
    }
    
    # Try a different endpoint that might be more reliable for Telugu content
    url = "https://www.jiosaavn.com/api.php?__call=content.getHomepageData&language=telugu&_format=json&_marker=0"
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = clean_jsonp(response.text)
                if not data:
                    return jsonify({"error": "Failed to parse telugu content"}), 500
                    
            # Simply return the parsed data directly
            return jsonify(data)
        else:
            return jsonify({"error": f"Telugu content request failed with status code: {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/telugu/new')
def get_telugu_new():
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "te-IN,te;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.jiosaavn.com/",
        "Cookie": "L=telugu"
    }
    
    # Try a different endpoint that might be more reliable for Telugu content
    url = "https://www.jiosaavn.com/api.php?__call=content.getNewReleases&language=telugu&_format=json&_marker=0"
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = clean_jsonp(response.text)
                if not data:
                    return jsonify({"error": "Failed to parse telugu content"}), 500
                    
            # Simply return the parsed data directly
            return jsonify(data)
        else:
            return jsonify({"error": f"Telugu content request failed with status code: {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/telugu/charts")
def telugu_charts():
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "te-IN,te;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.jiosaavn.com/featured/telugu",
        "Cookie": "L=telugu" 
    }
    
    url = "https://www.jiosaavn.com/api.php?_format=json&__call=content.getCharts&language=telugu"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            charts_data = response.json()
            return jsonify(charts_data)
        else:
            return jsonify({"error": "Failed to fetch Telugu charts", "status_code": response.status_code}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add this function to search specifically for Telugu songs
@app.route('/search/telugu')
def search_telugu_songs():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "te-IN,te;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.jiosaavn.com/",
        "Cookie": "L=telugu"  # Force Telugu language
    }
    
    # Add language=telugu parameter to ensure Telugu search results
    url = f"https://www.jiosaavn.com/api.php?__call=search.getResults&q={query}&_format=json&_marker=0&api_version=4&ctx=wap6dot0&n=20&p=1&languages=telugu"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            search_data = response.json()
            
            # Extract only Telugu songs
            telugu_songs = []
            for song in search_data.get('results', []):
                # Check if 'language' exists and is Telugu, or process all if language filtering is done server-side
                if 'language' in song and song['language'].lower() == 'telugu':
                    telugu_songs.append({
                        "id": song.get("id"),
                        "title": song.get("title"),
                        "artist": song.get("primary_artists", ""),
                        "album": song.get("album", ""),
                        "image": song.get("image", "").replace("150x150", "500x500"),
                        "url": song.get("perma_url", ""),
                        "language": "telugu"
                    })
                
            return jsonify({"results": telugu_songs, "total": len(telugu_songs)})
        else:
            return jsonify({"error": "API request failed", "status_code": response.status_code}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/check")
def check():
        import requests
        url = "https://www.jiosaavn.com/api.php?_format=json&__call=content.getCharts&language=te"
        print(requests.get(url).json())
        dataPrint =requests.get(url).json()
        return jsonify(dataPrint)
@app.route("/prema")
def prema():
    try:
        # Use your server's internal endpoint
        internal_url = "http://localhost:5100/result/?query=https://www.jiosaavn.com/featured/most-searched-songs-telugu/OEvOb-ZbGV-uCJW60TJk1Q__"
        
        response = requests.get(internal_url)
        data = response.json()
        
        # Extract just the perma_urls
        perma_urls = []
        if isinstance(data, list):  # If response is array of songs
            for song in data:
                perma_urls.append(song.get("perma_url"))
        elif isinstance(data, dict):  # If response is playlist/album object
            for song in data.get("songs", []):
                perma_urls.append(song.get("perma_url"))
        
        return jsonify({
            "status": "success",
            "count": len(perma_urls),
            "perma_urls": perma_urls
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
    
@app.route('/queue/search', methods=['GET'])
def search_and_queue():
    """Search for a song and get related songs as queue"""
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    try:
        # Search for the song
        search_results = jiosaavn.search_for_song(query, lyrics=False, songdata=True)
        
        if not search_results:
            return jsonify({"error": "No songs found"}), 404
        
        # Get the first result (most relevant)
        main_song = search_results[0]
        
        # Get related songs - wait for response
        related_songs = get_related_songs(main_song['id'])
        
        # Format related songs to match main song structure
        formatted_related = []
        for song in related_songs:
            formatted_related.append({
                **song,
                'album': song.get('album', 'Various Artists'),
                'perma_url': f"https://www.jiosaavn.com/song/{song['id']}",
                'media_preview_url': song['url'].replace('aac', 'preview').replace('_320.mp4', '_96_p.mp4'),
                '320kbps': 'true',
                'has_lyrics': 'false'
            })
        
        # Build the queue (main song first, then related)
        queue['tracks'] = [main_song] + formatted_related
        queue['current_index'] = 0
        queue['related_songs'] = formatted_related
        
        return jsonify({
            "status": "success",
            "main_song": main_song,
            "related_count": len(formatted_related),
            "queue": queue['tracks'],
            "current_playing": queue['tracks'][queue['current_index']]
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def get_related_songs(song_id):
    """Fetch related songs from JioSaavn"""
    try:
        # Updated endpoint to get more details including related songs
        url = f"https://www.jiosaavn.com/api.php?__call=song.getDetails&cc=in&_marker=0%3F_marker%3D0&_format=json&pids={song_id}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # Extract related songs from the response
        related_songs = []
        
        # Method 1: Try to get from 'more_info' first
        if 'songs' in data and len(data['songs']) > 0:
            song_data = data['songs'][0]
            if 'more_info' in song_data and 'related_songs' in song_data['more_info']:
                related = song_data['more_info']['related_songs']
                for song in related:
                    related_songs.append({
                        'id': song['id'],
                        'title': song.get('title', song.get('song', 'Unknown')),
                        'artist': song.get('primary_artists', 'Unknown'),
                        'image': song.get('image', '').replace('150x150', '500x500'),
                        'url': song.get('media_url', ''),
                        'duration': song.get('duration', '0')
                    })
        
        # Method 2: If no related songs found, try alternative API
        if not related_songs:
            alt_url = f"https://www.jiosaavn.com/api.php?__call=webradio.getSong&song_id={song_id}&_format=json"
            alt_response = requests.get(alt_url, headers=headers)
            alt_data = alt_response.json()
            
            if 'songs' in alt_data:
                for song in alt_data['songs']:
                    related_songs.append({
                        'id': song['id'],
                        'title': song.get('title', song.get('song', 'Unknown')),
                        'artist': song.get('primary_artists', 'Unknown'),
                        'image': song.get('image', '').replace('150x150', '500x500'),
                        'url': song.get('media_url', ''),
                        'duration': song.get('duration', '0')
                    })
        
        return related_songs[:10]  # Return maximum 10 related songs
    
    except Exception as e:
        print(f"Error getting related songs: {e}")
        return []
@app.route('/queue/next', methods=['GET'])
def next_track():
    """Get next song in queue"""
    if not queue['tracks']:
        return jsonify({"error": "Queue is empty"}), 400
    
    if queue['shuffle']:
        queue['current_index'] = random.randint(0, len(queue['tracks'])-1)
    else:
        queue['current_index'] = (queue['current_index'] + 1) % len(queue['tracks'])
    
    return jsonify({
        "current_index": queue['current_index'],
        "current_track": queue['tracks'][queue['current_index']]
    })

@app.route('/queue/status', methods=['GET'])
def queue_status():
    """Get current queue status"""
    return jsonify({
        "count": len(queue['tracks']),
        "current_index": queue['current_index'],
        "current_track": queue['tracks'][queue['current_index']] if queue['tracks'] else None,
        "shuffle": queue['shuffle'],
        "repeat": queue['repeat'],
        "related_songs": queue['related_songs']
    })

@app.route('/song/')
def search():
    lyrics = False
    songdata = True
    query = request.args.get('query')
    lyrics_ = request.args.get('lyrics')
    songdata_ = request.args.get('songdata')
    if lyrics_ and lyrics_.lower() != 'false':
        lyrics = True
    if songdata_ and songdata_.lower() != 'true':
        songdata = False
    if query:
        return jsonify(jiosaavn.search_for_song(query, lyrics, songdata))
    else:
        error = {
            "status": False,
            "error": 'Query is required to search songs!'
        }
        return jsonify(error)

@app.route('/song/get/')
def get_song():
    lyrics = False
    id = request.args.get('id')
    lyrics_ = request.args.get('lyrics')
    if lyrics_ and lyrics_.lower() != 'false':
        lyrics = True
    if id:
        resp = jiosaavn.get_song(id, lyrics)
        if not resp:
            error = {
                "status": False,
                "error": 'Invalid Song ID received!'
            }
            return jsonify(error)
        else:
            return jsonify(resp)
    else:
        error = {
            "status": False,
            "error": 'Song ID is required to get a song!'
        }
        return jsonify(error)

@app.route('/playlist/')
def playlist():
    lyrics = False
    query = request.args.get('query')
    lyrics_ = request.args.get('lyrics')
    if lyrics_ and lyrics_.lower() != 'false':
        lyrics = True
    if query:
        id = jiosaavn.get_playlist_id(query)
        songs = jiosaavn.get_playlist(id, lyrics)
        return jsonify(songs)
    else:
        error = {
            "status": False,
            "error": 'Query is required to search playlists!'
        }
        return jsonify(error)

@app.route('/album/')
def album():
    lyrics = False
    query = request.args.get('query')
    lyrics_ = request.args.get('lyrics')
    if lyrics_ and lyrics_.lower() != 'false':
        lyrics = True
    if query:
        id = jiosaavn.get_album_id(query)
        songs = jiosaavn.get_album(id, lyrics)
        return jsonify(songs)
    else:
        error = {
            "status": False,
            "error": 'Query is required to search albums!'
        }
        return jsonify(error)

@app.route('/lyrics/')
def lyrics():
    query = request.args.get('query')
    if query:
        try:
            if 'http' in query and 'saavn' in query:
                id = jiosaavn.get_song_id(query)
                lyrics = jiosaavn.get_lyrics(id)
            else:
                lyrics = jiosaavn.get_lyrics(query)
            response = {
                "status": True,
                "lyrics": lyrics
            }
            return jsonify(response)
        except Exception as e:
            error = {
                "status": False,
                "error": str(e)
            }
            return jsonify(error)
    else:
        error = {
            "status": False,
            "error": 'Query containing song link or id is required to fetch lyrics!'
        }
        return jsonify(error)

@app.route('/result/')
def result():
    lyrics = False
    query = request.args.get('query')
    lyrics_ = request.args.get('lyrics')
    if lyrics_ and lyrics_.lower() != 'false':
        lyrics = True

    if 'saavn' not in query:
        return jsonify(jiosaavn.search_for_song(query, lyrics, True))
    try:
        if '/song/' in query:
            song_id = jiosaavn.get_song_id(query)
            song = jiosaavn.get_song(song_id, lyrics)
            return jsonify(song)
        elif '/album/' in query:
            id = jiosaavn.get_album_id(query)
            songs = jiosaavn.get_album(id, lyrics)
            return jsonify(songs)
        elif '/playlist/' in query or '/featured/' in query:
            id = jiosaavn.get_playlist_id(query)
            songs = jiosaavn.get_playlist(id, lyrics)
            return jsonify(songs)
    except Exception as e:
        print_exc()
        error = {
            "status": True,
            "error": str(e)
        }
        return jsonify(error)
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, debug=True, use_reloader=True, threaded=True)