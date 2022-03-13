import requests
import logging
import coloredlogs
import concurrent
import json
import re
import types
import numpy as np
from collections import Counter
from dotenv import dotenv_values


coloredlogs.DEFAULT_FIELD_STYLES['levelname']['color'] = 'white'
DEBUG_LEVELV_NUM = 9
logging.addLevelName(DEBUG_LEVELV_NUM, "\U0001F3B5")
def notice(self, message, *args, **kws):
    self._log(DEBUG_LEVELV_NUM, message, args, **kws)
logging.Logger.notice = notice


m_headers = {
    'Accept':'Application/json'
}

class Logger():
    @property
    def logger(self):
        l = logging.Logger(type(self).__name__)
        l.setLevel(logging.INFO)
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = coloredlogs.ColoredFormatter(format_str)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        l.addHandler(ch)
        return l


class SpotifyAPI(Logger):
    def __init__(self):
        self.config = dotenv_values(".env") 
        required = ['SPOTIFY_API_URL','SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET','SPOTIFY_AUTH_URL']
        if not all(x in self.config for x in required):
            raise Exception(f"One or more of {required} is not in a .env file")

        self.__auth_url = self.config.get('SPOTIFY_AUTH_URL')
        self.__base_url = self.config.get('SPOTIFY_API_URL')

        self.logger.info(f"Setup SpotifyAPI with {self.__base_url}")

        self.__access_token = None
        self.__headers = None
        self.authorise()
        
    def authorise(self):
        auth_response = requests.post(self.__auth_url, {
            'grant_type': 'client_credentials',
            'client_id': self.config.get('SPOTIFY_CLIENT_ID'),
            'client_secret': self.config.get('SPOTIFY_CLIENT_SECRET')
        })

        # convert the response to JSON
        auth_response_data = auth_response.json()
        # save the access token
        self.__access_token = auth_response_data['access_token']

        self.__headers = {
            'Authorization': f'Bearer {self.__access_token}',
            'Accept':'Application/json'
        }
                
    def find_artist_id(self,name):
        url = f'{self.__base_url}search?q="{name}"&type=artist'
        retval = [(x['name'],x['id']) for x in requests.get(url,headers=self.__headers).json()['artists']['items']]
       
        if len(retval) == 0:
            raise Exception(f"couldn't find artist by name '{name}'")
        if len(retval) > 1:
            self.logger.warning(f"found multiple artists: {retval}. Using the first!")
        name,_id = retval[0]
        self.logger.info(f"found the artist '{name}' with id={_id}")
        return _id

    def get_albums(self,_id):
        url = f'{self.__base_url}artists/{_id}/albums'
        retval = [a['id'] for a in requests.get(url,headers=self.__headers).json()['items']]
        self.logger.info(f"found {len(retval)} albums")
        return retval

    def _clean_song_name(self,name):
        return name.split(" - ")[0]
    
    def get_songs(self,album_ids):
        album_ids = ','.join(album_ids)
        url = f'{self.__base_url}albums?ids={album_ids}'
        data = requests.get(url,headers=self.__headers).json()

        songs =  {
            self._clean_song_name(t['name']): {
                'release_date':a['release_date'],
                'track_number':t['track_number'],
            }
            for a in data['albums'] for t in a['tracks']['items']
        }
        self.logger.info(f"found {len(songs)} songs")
        return songs

    def find_songs(self,artist_name):
        artist_id = self.find_artist_id(artist_name)
        album_ids = self.get_albums(artist_id)
        return self.get_songs(album_ids)


class LyricsAPI(Logger):
    def __init__(self):
        self.__base_url = 'https://api.lyrics.ovh/v1'
        self.logger.info(f"Setup LyricsAPI with {self.__base_url}")
                
    def get_lyrics(self,artist_name,song_name):
        url = f'{self.__base_url}/{artist_name}"/"{song_name}"'
        self.logger.debug(f'trying {url}')
        try:
            res = requests.get(url=url,headers=m_headers)
        except requests.exceptions.ConnectionError as e:
            self.logger.error(e)
            self.logger.error(f'failed to get a response for {song_name}')
            return None
        lyrics = res.json()['lyrics'] if res.status_code==200 else None
        if lyrics == None:
            self.logger.warning(f'failed to get lyrics for {song_name}')
            return None
        self.logger.info(f'successfully got {song_name} for {artist_name}')
        return lyrics

    
class Lyrix(SpotifyAPI,LyricsAPI):
    def __init__(self):
        SpotifyAPI.__init__(self)
        LyricsAPI.__init__(self)
        self.__cache = {}
        
    def _extract_words(self,lyrics):
        return [re.sub('[^a-zA-Z]+', '', w.lower()) for w in re.split('\s+', lyrics)]
    
    def calculate_average_n_words(self,artist_name):
        artist = self.get(artist_name)
        stats = artist.stats
        
        self.logger.info("")
        self.logger.info("--- Words ---")
        self.logger.info(json.dumps(stats['number_of_words'],indent=6))
      
        
    def get(self,artist_name,**kwargs):
        if artist_name in self.keys():
            return self[artist_name]
        
        songs = self.find_songs(artist_name)
        song_names = list(songs.keys())
        all_lyrics = self.get_all_lyrics(song_names,artist_name,**kwargs)
        if not all_lyrics:
            self.logger.error(f"Could not find any lyrics for '{artist_name}'!")
            return

        for k,v in songs.items():
            v.update({'lyrics':all_lyrics[k]})
           
        words = self.get_words(songs)
        stats = self.calculate_stats(songs,words)

        artist = types.SimpleNamespace(name=artist_name,
                                       songs=songs,
                                       words=words,
                                       stats=stats)

        self[artist_name] = artist
        return self[artist_name]

    def keys(self):
        return self.__cache.keys()

    def items(self):
        return self.__cache.items()
    
    def __setitem__(self,key,obj):
        self.__cache[key] = obj
        
    def __getitem__(self,key):
        return self.__cache[key]

    def get_all_cached_artists(self):
        return self.__cache
            
    def calculate_stats(self,songs,words):
        nwords = np.array([s['nwords'] for s in words])
        return {
            'nsongs':len(songs),
            'nsongs_lyrics_found':len(words),
            'number_of_words': {
                'mean': round(nwords.mean(),2),
                'std': round(nwords.std(),2),
                'variance': round(nwords.var(),2),
                'min': {
                    'value':int(nwords.min()),
                    'song':words[nwords.argmin()]['song_name']
                },
                'max': {
                    'value':int(nwords.max()),
                    'song':words[nwords.argmax()]['song_name']
                }
            }if nwords.size else None
        }
        
    def get_words(self,songs):
        words = [
            {
                'song_name':song_name,
                'nwords': len(words),
                'unique_words': dict(Counter(words).most_common())
            }
            for song_name,info in songs.items()
            if info['lyrics'] and (words := self._extract_words(info['lyrics']))
        ]
        return words

    def get_all_lyrics(self,songs,artist_name,nthreads=200):
        with concurrent.futures.ThreadPoolExecutor(max_workers=nthreads) as executor: 
            res = {
                executor.submit(self.get_lyrics, artist_name, song_name) : song_name
                for song_name in songs
            }
            
            all_lyrics = {
                res[future]:future.result() 
                for future in concurrent.futures.as_completed(res)
            }
            return all_lyrics

                       
    def find_and_print_songs(self,artist_name):
        songs = self.find_songs(artist_name)
        self.logger.notice("Found the following songs...")
        for i,line in enumerate(songs):
            self.logger.notice(f"{i}: {line}")
        
    
    def search(self,artist_name,song_name):
        lyrics = self.get_lyrics(artist_name,song_name)
        self.logger.notice("=====================")
        for line in lyrics.splitlines():
            self.logger.notice(line)
        
