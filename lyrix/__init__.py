import requests
import logging
import coloredlogs
import concurrent.futures
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



class Logger():
    """
    A class to enable inheritance of a custom message logger
    """
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
    """
    A simple class for the interacting with the Spotify free API to retreive data on a given artist
    """
    def __init__(self):
        #load the .env file to contain client id and secrets..
        self.config = dotenv_values(".env") 
        required = ['SPOTIFY_API_URL','SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET','SPOTIFY_AUTH_URL']
        if not all(x in self.config for x in required):
            raise Exception(f"One or more of {required} is not in a .env file")

        #setu URLs to be used
        self.__auth_url = self.config.get('SPOTIFY_AUTH_URL')
        self.__base_url = self.config.get('SPOTIFY_API_URL')

        self.logger.info(f"Setup SpotifyAPI with {self.__base_url}")

        self.__access_token = None
        self.__headers = None
        self.authorise()

    def _clean_song_name(self,name):
        """
        Clean a song name, if there's a '-' in the name, split on this and take the first part
        This is a common occurrence in Spotify where for older songs, the name has a date of remastered version
        appended... therefore we dont want to count the same song twice (old and remastered version)
        """
        return name.split(" - ")[0]
        
    def authorise(self):
        """
        Calls the authorisation URL to return an access token that is valide for ~60 minutes
        Also sets a global header that can be used in calls to the main API url
        """
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
        """
        Find an artist's ID (on spotify) by passing the name of an artist

        Args:
           name (str) : the name of an artist
        Returns:
           str: spotify artist identifier
        """
        #use the url to search for an artist give the name
        url = f'{self.__base_url}search?q="{name}"&type=artist'
        #extract just the name and the ID from this returned data
        retval = [(x['name'],x['id']) for x in requests.get(url,headers=self.__headers).json()['artists']['items']]
        #if nothing returned... cant fidn the artist
        if len(retval) == 0:
            raise Exception(f"couldn't find artist by name '{name}'")
        #warn if more than one artist found
        if len(retval) > 1:
            self.logger.warning(f"found multiple artists: {retval}. Using the first!")
        #return the first artist found (most likely to be the artist requested)
        name,_id = retval[0]
        self.logger.info(f"found the artist '{name}' with id={_id}")
        return _id

    def get_albums(self,_id):
        """
        Find albums for an artist
        
        Args:
          _id (str) : hash IDs of the artist on spotify
        Returns:
          list : a list of all album IDs
        """
        url = f'{self.__base_url}artists/{_id}/albums'
        retval = [a['id'] for a in requests.get(url,headers=self.__headers).json()['items']]
        self.logger.info(f"found {len(retval)} albums")
        return retval

    
    def get_songs(self,album_ids):
        """
        Get all songs given multiple albumn ids

        Args:
           album_ids (list) : a list of hashed albumn ids (str)
        Returns:
           dict : a lookup between a song name and the track number and release date
        """
        #concat all album ids into a comma separated string
        #this is useful to hit the api with one request,
        #rather than one request per albumn
        album_ids = ','.join(album_ids)
        url = f'{self.__base_url}albums?ids={album_ids}'
        data = requests.get(url,headers=self.__headers).json()

        #organise the data
        #loop over all albumns
        #loop over all tracks in each album
        #create a look up between the song name (cleaned)
        #and some data about the track 
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
        """
        Find all songs given an artist name
        Args:
          artist_name (str) : the name of the artist
        Returns:
          dict : see return value of get_songs() 
        """
        artist_id = self.find_artist_id(artist_name)
        album_ids = self.get_albums(artist_id)
        return self.get_songs(album_ids)


class LyricsAPI(Logger):
    """
    A simple class for the interacting with the API to retrieve lyrics
    """
    def __init__(self):
        """
        Initialise the class, setting up the base URL and any headers to be used
        """
        #API base to hit
        self.__base_url = 'https://api.lyrics.ovh/v1'
        self.logger.info(f"Setup LyricsAPI with {self.__base_url}")

        #basic headers
        self.__headers = {
            'Accept':'Application/json'
        }
        
    def get_lyrics(self,artist_name,song_name):
        """
        Retrieve lyrics given an artist and song name

        Args:
          artist_name (str): the name of the artist
          song_name (str): the name of the song
        Returns:
          str: the lyrics returned by the API, unaltered
        """
        
        url = f'{self.__base_url}/{artist_name}"/"{song_name}"'
        self.logger.debug(f'trying {url}')
        #try and retrieve the lyrics for the song
        try:
            res = requests.get(url=url,headers=self.__headers)
        except requests.exceptions.ConnectionError as e:
            self.logger.error(e)
            self.logger.error(f'failed to get a response for {song_name}')
            return None
        #extract the lyrics from the response 
        lyrics = res.json()['lyrics'] if res.status_code==200 else None
        if lyrics == None:
            self.logger.warning(f'failed to get lyrics for {song_name}')
            return None
        self.logger.info(f'successfully got {song_name} for {artist_name}')
        return lyrics

    
class Lyrix(SpotifyAPI,LyricsAPI):
    """
    Lyrix class for obtaining song data of multiple artitsts
    
    The class inherits from two backends:
    * SpotifyAPI - for getting data on an artist (albumns, songs, etc.)
    * LyricsAPI - for getting lyrics from a given song

    Note: these backends can be changed in the future to use different APIs

    """
    def __init__(self):
        """
        Initialise the class by initialising the two backend APIs
        """
        SpotifyAPI.__init__(self)
        LyricsAPI.__init__(self)
        #create a dict that can be used to cache data
        self.__cache = {}
        
    def _extract_words(self,lyrics):
        """
        Extract words from a song given the lyrics

        * splits the lyrics on white space (space, tabs, linebreaks etc.) 
        * loops over each split word
        * puts each words into lower case
        * removes any non-alphanumeric characters from the word (e.g. brackets)

        Args:
          lyrics (str) : full lyrics returned from the API call
        Returns:
          list: a list of cleaned words from the lyrics
        """
        return [re.sub('[^a-zA-Z]+', '', w.lower()) for w in re.split('\s+', lyrics)]
    
             
    def get(self,artist_name,**kwargs):
        """
        Get data on artist by processing the name:
        * get all songs
        * get all lyrics 
        * get words
        * calculate the statistics 
        * create an artist object 
        * cache the artist object
        * return the artist object
                
        Args:
          artist_name (str) : the name of an artist
          **kwargs (dict,optional) : additional keyword arguments to pass 
        Returns:
          SimpleNamespace : an object that stores the data of a processed artist

        """

        #if already processed, dont run again, return the cached artist
        if artist_name in self.keys():
            return self[artist_name]

        #find all songs
        songs = self.find_songs(artist_name)
        song_names = list(songs.keys())
        #from the song names, get all the lyrics
        all_lyrics = self.get_all_lyrics(song_names,artist_name,**kwargs)
        if not all_lyrics:
            self.logger.error(f"Could not find any lyrics for '{artist_name}'!")
            return
        #appends the lyrics data to the songs
        for k,v in songs.items():
            v.update({'lyrics':all_lyrics[k]})

        #extract the words from the songs
        words = self.get_words(songs)
        #calculate statitics on the songs/words
        stats = self.calculate_stats(songs,words)

        #save an artist as a simplenamespace object
        artist = types.SimpleNamespace(name=artist_name,
                                       songs=songs,
                                       words=words,
                                       stats=stats)
        #save to the cache
        self[artist_name] = artist
        #return the artist
        return self[artist_name]

    def keys(self):
        """
        return the names of the artists already saved in the cache
        """
        return self.__cache.keys()

    def items(self):
        """
        return all items in the cache (useful for looping)
        """
        return self.__cache.items()
    
    def __setitem__(self,key,obj):
        """
        set an item in the cache 
        """
        self.__cache[key] = obj
        
    def __getitem__(self,key):
        """
        get an item from the cache
        """
        return self.__cache[key]

    def get_all_cached_artists(self):
        """
        return the private object for the cache
        """
        return self.__cache
            
    def calculate_stats(self,songs,words):
        """
        Calculate the statistics give song and words
        Args:
           song (dict): a map of all songs 
           words (list): a list for each song containing the data on words in that song
        """
        #extract the number of words in each song
        nwords = np.array([s['nwords'] for s in words])
        #create and return some data on these words
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
        """
        get and return words given all songs
        Args:
           songs (dict): a lookup of {song_name:song_data} for all songs
        Return:
           list: for each song, some data on the words
        """
        #loop over all songs
        # * if lyrics are present for a song
        # * and the words could be extracted from the lyrics
        # * append new data for the number of words, and a counter of the most common words
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
        """
        get all lyrics from all songs

        by default, multithreading is used to speed up the retrieval of all lyrics of all songs

        Args:
           songs (dict) : a map of all song names and some song data
           artist_name (str) : the name of an artist
           nthreads (int): the number of threads to multithread with [default=200]
        
        Returns:
          dict : a lookup between a song name and its lyrics
        """
        #initiate a thread pool 
        with concurrent.futures.ThreadPoolExecutor(max_workers=nthreads) as executor:
            #define and submit multiple threads for retrieve the lyrics for each song
            res = {
                executor.submit(self.get_lyrics, artist_name, song_name) : song_name
                for song_name in songs
            }
            #wait for all threads to complete and return a look up dictionary between the
            #song name and the returned lyrics
            all_lyrics = {
                res[future]:future.result() 
                for future in concurrent.futures.as_completed(res)
            }
            return all_lyrics

                       
    def find_and_print_songs(self,artist_name):
        """
        Simple function for find and print all songs given an artist
        Args:
          artist_name (str) : name of an artist
        """
        songs = self.find_songs(artist_name)
        self.logger.notice("Found the following songs...")
        for i,line in enumerate(songs):
            self.logger.notice(f"{i}: {line}")
        
    
    def search(self,artist_name,song_name):
        """
        Simple function to search for lyrics given an artist name and song name
        """
        lyrics = self.get_lyrics(artist_name,song_name)
        self.logger.notice("=====================")
        for line in lyrics.splitlines():
            self.logger.notice(line)
        
    def calculate_average_n_words(self,artist_name):
        """
        Given an artist name, print the statistics on the number of words of their songs
        Args:
           artist_name (str) : the name of an artist
        """
        artist = self.get(artist_name)
        stats = artist.stats
        
        self.logger.info("")
        self.logger.info("--- Words ---")
        self.logger.info(json.dumps(stats['number_of_words'],indent=6))
