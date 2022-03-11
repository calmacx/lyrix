import requests
import logging
import coloredlogs
import concurrent
import json
import re
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
        return requests.get(url,headers=self.__headers).json()['artists']['items'][0]['id']

    def get_albums(self,_id):
        url = f'{self.__base_url}artists/{_id}/albums'
        return [a['id'] for a in requests.get(url,headers=self.__headers).json()['items']]

    def get_songs(self,album_ids):
        album_ids = ','.join(album_ids)
        url = f'{self.__base_url}albums?ids={album_ids}'
        data = requests.get(url,headers=self.__headers).json()
        songs =  [t['name'] for a in data['albums'] for t in a['tracks']['items']]
        clean_songs = list(set([s.split(" - ")[0] for s in songs]))
        return clean_songs

    def find_songs(self,artist_name):
        artist_id = self.find_artist_id(artist_name)
        album_ids = self.get_albums(artist_id)
        return self.get_songs(album_ids)

    
class Lyrix(SpotifyAPI):
    def __init__(self):
        super().__init__()

    def get_words(self,lyrics):
        return [re.sub('[^a-zA-Z]+', '', w.lower()) for w in re.split('\s+', lyrics)]

    def calculate_average_n_words(self,artist_name):
        songs = self.find_songs(artist_name)
        all_lyrics = self.get_all_lyrics(songs,artist_name)
        summary = self.summarise(all_lyrics)
        stats = self.calculate_stats(summary)
        self.logger.info("")
        self.logger.info("--- Statistics ---")
        self.logger.info(json.dumps(stats,indent=6))
        
    def calculate_stats(self,summary):
        nwords = np.array([s['nwords'] for s in summary['songs']])
        return {
            'nsongs':len(summary['songs']),
            'average_number_of_words':round(nwords.mean(),2),
            'std_number_of_words':round(nwords.std(),2),
            'min_number_of_words':int(nwords.min()),
            'min_song_name':summary['songs'][nwords.argmin()]['name'],
            'max_number_of_words':int(nwords.max()),
            'max_song_name':summary['songs'][nwords.argmax()]['name'],
        }
        
    def summarise(self,all_lyrics):
        retval = {
            'nsongs':len(all_lyrics),
            'songs': [
                {
                    'name':song_name,
                    'nwords': len(words),
                    'words': dict(Counter(words).most_common())
                }
                for song_name,lyrics in all_lyrics.items()
                if (words := self.get_words(lyrics))
            ]
        }
        return retval

    def get_all_lyrics(self,songs,artist_name,nthreads=200):
        with concurrent.futures.ThreadPoolExecutor(max_workers=nthreads) as executor: 
            res = {
                executor.submit(self.get_lyrics, artist_name, song_name) : song_name
                for song_name in songs
            }
            
            all_lyrics = {
                res[future]:future.result() 
                for future in concurrent.futures.as_completed(res)
                if future.result()
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
        
    def get_lyrics(self,artist_name,song_name):
        url = f'https://api.lyrics.ovh/v1/"{artist_name}"/"{song_name}"'
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
