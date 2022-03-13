# Lyrix

A command line tool for searching for lyrics and analysing lyrics of given artist(s) 


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

For example, to find a song:
```

```
