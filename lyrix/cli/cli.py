#from .subcommands.info import info
import click
import json


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
    

        
#coconnect.add_command(etl, "etl")
#coconnect.add_command(airflow,'airflow')



if __name__ == "__main__":
    lyrix()
