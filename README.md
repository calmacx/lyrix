# Lyrix

A python module for searching for lyrics and analysing lyrics of given artist(s).

Lyrix can be imported as a python class to more control, or the Command Line Interface (CLI) can be used.

Lyrix used the Spotify API as a backend to retrieve songs of a given artist.

Follow this README for a guide on how to use the CLI, for the python module - follow the `jupyter` notebook [provided here](https://github.com/calmacx/lyrix/blob/master/notebooks/Analysis.ipynb).

## Installation

Get the source code:
```
git clone https://github.com/calmacx/lyrix.git
```

Setup a virtual environment (optional, otherwise used python `>=3.8`)
```
python3 -m venv .
source bin/activate
```

Install the cloned folder from git:
```
pip install pip --upgrade
pip install -e ./lyrix
```

## Setup Env file

To be able to use this package with the SpotifyAPI, you will need to set the following variables in a `.env` file where the code/CLI is executed from.
```
SPOTIFY_CLIENT_ID = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
SPOTIFY_CLIENT_SECRET = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_URL = 'https://api.spotify.com/v1/'
```

You will need a Spotify developer account (free), instruction for setting this up and obtaining a client ID and secret [can be found here.](https://developer.spotify.com/documentation/web-api/quick-start/).

If you do not, you will see the error:
```
Exception: One or more of ['SPOTIFY_API_URL', 'SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_AUTH_URL'] is not in a .env file
```


## Command Line Interface

To show the available options of the command line tool:
```
$ lyrix --help
Usage: lyrix [OPTIONS] COMMAND [ARGS]...

  Command line tool for searching for lyrics

Options:
  -l, --log-level [0|1|2|3]  change the level for log messaging. 0 - ERROR, 1
                             - WARNING, 2 - INFO (default), 3 - DEBUG
  --help                     Show this message and exit.

Commands:
  find-songs  A simple command to get all song by a given artist
  get         Commands that can be used to get/retrieve data
  search      Simple command to search for lyrics give a song name and an...
```

### find songs

For example, to find songs of a given artist:
```
$ lyrix find-songs --artist Radiohead

2022-03-13 20:54:43 - Lyrix - INFO - Setup SpotifyAPI with https://api.spotify.com/v1/
2022-03-13 20:54:43 - Lyrix - INFO - Setup LyricsAPI with https://api.lyrics.ovh/v1
2022-03-13 20:54:44 - Lyrix - WARNING - found multiple artists: [('Radiohead', '4Z8W4fKeB5YxbusRsdQVPb'), ('DJ Radiohead', '5gfqeKQikBQqSZcOwSTE5w'), ('DJ Radiohead', '17mBFWKyCyp506a3n6XUWA'), ('Dj Radiohead', '54FnvKUQFU2KpNJlZi25G0'), ('Radiohead Tribute Band', '0ADkBHZhR2cVfANgK5gHQO')]. Using the first!
2022-03-13 20:54:44 - Lyrix - INFO - found the artist 'Radiohead' with id=4Z8W4fKeB5YxbusRsdQVPb
2022-03-13 20:54:44 - Lyrix - INFO - found 20 albums
2022-03-13 20:54:44 - Lyrix - INFO - found 140 songs
2022-03-13 20:54:44 - Lyrix - 🎵 - Found the following songs...
2022-03-13 20:54:44 - Lyrix - 🎵 - 0: Everything In Its Right Place
2022-03-13 20:54:44 - Lyrix - 🎵 - 1: Kid A
...
2022-03-13 20:54:44 - Lyrix - 🎵 - 136: Supercollider
2022-03-13 20:54:44 - Lyrix - 🎵 - 137: The Butcher
2022-03-13 20:54:44 - Lyrix - 🎵 - 138: Harry Patch (In Memory Of)
2022-03-13 20:54:44 - Lyrix - 🎵 - 139: Spectre
```

### search for song lyrics

Given an artist and a song title:
```
$ lyrix search -a Radiohead -s 'Creep'

2022-03-13 20:56:14 - Lyrix - INFO - Setup SpotifyAPI with https://api.spotify.com/v1/
2022-03-13 20:56:14 - Lyrix - INFO - Setup LyricsAPI with https://api.lyrics.ovh/v1
2022-03-13 20:56:15 - Lyrix - INFO - successfully got Creep for Radiohead
2022-03-13 20:56:15 - Lyrix - 🎵 - =====================
2022-03-13 20:56:15 - Lyrix - 🎵 - When you were here before
2022-03-13 20:56:15 - Lyrix - 🎵 - Couldn't look you in the eye
2022-03-13 20:56:15 - Lyrix - 🎵 - You're just like an angel
2022-03-13 20:56:15 - Lyrix - 🎵 - Your skin makes me cry
...
2022-03-13 20:56:15 - Lyrix - 🎵 - I don't belong here.
2022-03-13 20:56:15 - Lyrix - 🎵 - 
2022-03-13 20:56:15 - Lyrix - 🎵 - I don't belong here.
```

### get statistics for an artist

For an artist, retrieve all albums and then songs, find as many lyrics for these songs as possible, calculate and print the statistics of the lyrics such as the average number of words.
```
$ lyrix get statistics -a 'Radiohead'

2022-03-13 20:59:33 - Lyrix - INFO - Setup SpotifyAPI with https://api.spotify.com/v1/
2022-03-13 20:59:33 - Lyrix - INFO - Setup LyricsAPI with https://api.lyrics.ovh/v1
2022-03-13 20:59:33 - Lyrix - WARNING - found multiple artists: [('Radiohead', '4Z8W4fKeB5YxbusRsdQVPb'), ('DJ Radiohead', '5gfqeKQikBQqSZcOwSTE5w'), ('DJ Radiohead', '17mBFWKyCyp506a3n6XUWA'), ('Dj Radiohead', '54FnvKUQFU2KpNJlZi25G0'), ('Radiohead Tribute Band', '0ADkBHZhR2cVfANgK5gHQO')]. Using the first!
2022-03-13 20:59:33 - Lyrix - INFO - found the artist 'Radiohead' with id=4Z8W4fKeB5YxbusRsdQVPb
2022-03-13 20:59:34 - Lyrix - INFO - found 20 albums
2022-03-13 20:59:34 - Lyrix - INFO - found 140 songs
...
2022-03-13 20:59:36 - Lyrix - INFO - successfully got Pyramid Song for Radiohead
2022-03-13 20:59:36 - Lyrix - INFO - successfully got I Might Be Wrong for Radiohead
2022-03-13 20:59:36 - Lyrix - INFO - successfully got Optimistic for Radiohead
...
2022-03-13 21:00:10 - Lyrix - WARNING - failed to get lyrics for Good Evening Mrs Magpie
{
      "nsongs": 140,
      "nsongs_lyrics_found": 117,
      "number_of_words": {
            "mean": 121.06,
            "std": 62.85,
            "variance": 3949.53,
            "min": {
                  "value": 1,
                  "song": "Hunting Bears"
            },
            "max": {
                  "value": 301,
                  "song": "A Wolf At the Door"
            }
      }
}
```


## [Analysis Notebook](https://github.com/calmacx/lyrix/blob/master/notebooks/Analysis.ipynb)

For a more detailed analysis and comparison of artists, see the `jupyter` notebook.
