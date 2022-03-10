#from .subcommands.info import info
import click
import json
from lyrix import Lyrix

@click.group()
@click.option("--log-level","-l",
              type=click.Choice(['0','1','2','3']),
              default='2',
              help="change the level for log messaging. 0 - ERROR, 1 - WARNING, 2 - INFO (default), 3 - DEBUG ")
@click.pass_context
def lyrix(ctx,log_level):
    """
    Command line tool for searching for lyrics
    """
    lyrix = Lyrix()
    ctx.obj = lyrix

@click.command(help="Simple command to search for lyrics give a song name and an artist")
@click.option("--artist","-a",required=True,help="name of an artist")
@click.option("--song","-s",required=True,help="name of the song")
@click.pass_obj
def search(obj,artist,song):
    obj.search(artist,song)    

@click.command(help="A simple command to get all song by a given artist")
@click.option("--artist","-a",required=True,help="name of an artist")
@click.pass_obj
def find_songs(obj,artist):
    obj.find_and_print_songs(artist)



    
lyrix.add_command(search, "search")
lyrix.add_command(find_songs, "find-songs")

@click.group()
@click.pass_context
def get(ctx):
    pass

@click.command(help="Command to get the average number of words in all songs, given an artist name")
@click.option("--artist","-a",required=True,help="name of an artist")
@click.pass_obj
def average_n_words(obj,artist):
    obj.calculate_average_n_words(artist)

get.add_command(average_n_words,'average-number-of-words')

lyrix.add_command(get, "get")
#coconnect.add_command(airflow,'airflow')



if __name__ == "__main__":
    lyrix()
