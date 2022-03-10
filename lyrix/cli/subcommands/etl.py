import click
import inquirer
import signal

import os
try:
    import daemon
    from daemon.pidfile import TimeoutPIDLockFile
except ImportError:
    #this package is not supported in Windows
    #latest version gives an import error of package pwd
    #https://stackoverflow.com/questions/39366261/python27win-import-daemon-but-there-is-an-error-no-module-named-pwd
    daemon = None

import lockfile
import shutil
import io
import time
import datetime
import yaml
import json
import copy
import pandas as pd

import coconnect
from coconnect.tools.bclink_helpers import BCLinkHelpers
from coconnect.tools.logger import _Logger as Logger

from .map import run 
from .pseudonymise import pseudonymise

class PlatformNotSupported(Exception):
    pass

class UserNotSupported(Exception):
    pass

class DuplicateDataDetected(Exception):
    pass

class UnknownConfigurationSetting(Exception):
    pass

class MissingRulesFile(Exception):
    pass

class BadRulesFile(Exception):
    pass

#@click.group(invoke_without_command=True,help='Command group for running the full ETL of a dataset')
@click.group(help='Command group for running the full ETL of a dataset')
@click.option('config_file','--config','--config-file',help='specify a yaml configuration file',required=True)
@click.pass_context
def etl(ctx,config_file):
    config = _load_config(config_file)
    ctx.obj = config
    #if ctx.invoked_subcommand == None:
    #    print ("no invoked subcommand")
    #    ctx.invoke(bclink)
    #else:
    #    pass


def _load_config(config_file):
    stream = open(config_file) 
    config = yaml.safe_load(stream)
    return config

@click.group(help='Command group for ETL integration with bclink')
@click.option('--force','-f',help='Force running of this, useful for development purposes',is_flag=True)
@click.option('--interactive','-i',help='run with interactive options - i.e. so user can confirm operations',is_flag=True)
@click.pass_context
@click.pass_obj
def bclink(ctx,obj,force,interactive):
    print (ctx)
    print (obj)
    exit(0)
    if not force:
        #check the platform (i.e. should be centos)
        if os.name == 'nt':
            raise PlatformNotSupported(f"Not suported to run this on Windows")
        #check the username
        #for bclink, we need to run as bcos_srv to get access to all the datasettool2 etc. tools
        #and be able to connect with the postgres server without the need for a password
        user = os.environ.get("USER")
        if user != 'bcos_srv':
            raise UserNotSupported(f"{user} not supported! You must run this as user 'bcos_srv'")


    config = _load_config(config_file)
    #put in protection for missing keys
    if 'rules' not in config:
        raise MissingRulesFile(f"you must specify a json rules file in your '{config_file}'"
                               f" via 'rules:<path of file>'")

    try:
        rules = coconnect.tools.load_json(config['rules'])
        destination_tables = list(rules['cdm'].keys())
    except Exception as e:
        raise BadRulesFile(e)
    
    bclink_settings = {}
    if 'bclink' in config:
        bclink_settings = config.pop('bclink')
    
    if 'tables' not in bclink_settings:
        bclink_settings['tables'] = {x:x for x in destination_tables}

    if 'global_ids' not in bclink_settings:
        #change default behaviour to non-table
        bclink_settings['global_ids'] = None#'global_ids'

    bclink_settings['tables'] = _get_table_map(bclink_settings['tables'],destination_tables)
    bclink_helpers = BCLinkHelpers(**bclink_settings)
    if ctx.obj is None:
        ctx.obj = dict()
    ctx.obj['bclink_helpers'] = bclink_helpers
    ctx.obj['rules'] = rules
    ctx.obj['data'] = config['data']
   
    log = 'coconnect.log'
    if 'log' in config.keys():
        log = config['log']
    ctx.obj['log'] = log
    ctx.obj['conf'] = config_file

    clean = False
    if 'clean' in config.keys():
        clean = config['clean']
    ctx.obj['clean'] = clean

    ctx.obj['interactive'] = interactive
    
    if 'pseudonymise' in config:
        ctx.obj['pseudonymise'] = config['pseudonymise']

    #define the default steps to execute
    ctx.obj['steps']=['clean','extract','transform','load']

    unknown_keys = list( set(config.keys()) - set(ctx.obj.keys()) )
    if len(unknown_keys) > 0 :
        raise UnknownConfigurationSetting(f'"{unknown_keys}" are not valid settings in the yaml file')

def _process_data(ctx):
    data = ctx.obj['data']
    if isinstance(data,list):
        _process_list_data(ctx)
    else:
        _process_dict_data(ctx)
    
def _process_list_data(ctx):
    logger = Logger("_process_list_data")
    logger.info("ETL process has begun")
   
    interactive = ctx.obj['interactive']
    data = []
    clean = ctx.obj['clean']
    rules = ctx.obj['rules']
    bclink_helpers = ctx.obj['bclink_helpers']
    config_file = ctx.obj['conf']
    conf = _load_config(config_file)
    rules_file = conf['rules']
    rules_file_last_modified = os.path.getmtime(rules_file) 
    
    bclink_helpers.print_summary()
    display_msg = True
    _clean = clean

    while True:
        
        re_execute = False
        try:
            conf = _load_config(config_file)
        except Exception as e:
            if not display_msg:
                logger.critical(e)
                logger.error(f"You've misconfigured your file '{config_file}'!! Please fix!")
            time.sleep(5)
            display_msg = True
            continue

        current_rules_file = conf['rules']
        new_rules_file = rules_file != current_rules_file
        if new_rules_file:
            #if there's a new rules file
            logger.info(f"Detected a new rules file.. old was '{rules_file}' and new is '{current_rules_file}'")
            rules_file = current_rules_file
            rules = coconnect.tools.load_json_delta(rules_file,rules)
            rules_file_last_modified = os.path.getmtime(rules_file)
            re_execute = True
        else: 
            #otherwise check for changes in the existing file
            new_rules_file_last_modified = os.path.getmtime(current_rules_file)
            change_in_rules = rules_file_last_modified != new_rules_file_last_modified
            if change_in_rules:
                logger.info(f"Detected a change/update in the rules file '{rules_file}'")
                rules = coconnect.tools.load_json_delta(current_rules_file,rules)
                re_execute = True 
            
        current_data = conf['data']
        if not data == current_data:
            logger.debug(f"old {data}")
            logger.debug(f"new {current_data}")
            new_data = [obj for obj in current_data if obj not in data]
            logger.info(f"New data found! {new_data}")
            re_execute = True
        else:
            new_data = data

        logger.debug(f"re-execute {re_execute}")
        if re_execute:
            current_data = copy.deepcopy(new_data)
            #loop over any new data
            for item in new_data:
                if isinstance(item['input'],list):
                    inputs = item['input']
                else:
                    input_folder = item['input']
                    if not os.path.isdir(input_folder):
                        raise Exception(f"{input_folder} is not a directory containing files!")
                    inputs = coconnect.tools.get_files(input_folder,type='csv')
                filtered_rules = coconnect.tools.remove_missing_sources_from_rules(rules,inputs)

                _execute(ctx,
                         data=item,
                         rules=filtered_rules,
                         clean=_clean
                     )
                _clean = False
            
            data += [x for x in current_data if x not in data]
            display_msg=True
       

        if new_rules_file or change_in_rules:
            #if there's a new rules file or rules delta,
            #need to pick up the full rules for the next loop
            #incase we insert new data
            # --> we dont want to just apply the delta to the new data
            rules = coconnect.tools.load_json(current_rules_file)
       
        if ctx.obj['listen_for_changes'] == False:
            break
    
        if display_msg:
            logger.info(f"Finished!... Listening for changes to data in {config_file}")
            if display_msg:
                display_msg = False
    
        time.sleep(5)
        

def _process_dict_data(ctx):
    logger = Logger("_process_dict_data")
    logger.info("ETL process has begun")

    interactive = ctx.obj['interactive']
    data = ctx.obj['data']
    clean = ctx.obj['clean']
    rules = ctx.obj['rules']
    bclink_helpers = ctx.obj['bclink_helpers']
    
    bclink_helpers.print_summary()

    #calculate the amount of time to wait before checking for changes
    tdelta = None
    if 'watch' in data:
        watch = data['watch']
        tdelta = datetime.timedelta(**watch)
        
    #get the input folder to watch
    input_folder = data['input']
    #get the root output folder
    output_folder = data['output']

                
    i = 0
    while True:
        #find subfolders containing data dumps
        subfolders = coconnect.tools.get_subfolders(input_folder)
        # if len(subfolders)>0:
        #     logger.info(f"Found {len(subfolders)} subfolders at path '{input_folder}'")
        # if interactive and len(subfolders)>0:
        #     questions = [
        #         inquirer.Checkbox('folders',
        #                           message="Confirm processing the following subfolders.. ",
        #                           choices=subfolders,
        #                           default=subfolders
        #                           )
        #         ]
        #     answers = inquirer.prompt(questions)
        #     if answers == None:
        #         os.kill(os.getpid(), signal.SIGINT)
            
        #     subfolders = {k:v for k,v in subfolders.items() if k in answers['folders']}
        #     logger.info(f"selected {subfolders}")
        
        logger.debug(f"Found and checking {len(subfolders.values())} subfolders")
        logger.debug(list(subfolders.values()))
  
        if len(subfolders.values())> 0:
            logger.debug(f"{list(subfolders.values())}")
                  
        njobs=0
        #print (reversed(sorted(subfolders.items(),key=lambda x: os.path.getmtime(x[1]))))
        for name,path in sorted(subfolders.items(),key=lambda x: os.path.getmtime(x[1])):
            output_folder_exists = os.path.exists(f"{output_folder}/{name}")
  
            inputs = coconnect.tools.get_files(path,type='csv')
            filtered_rules = coconnect.tools.remove_missing_sources_from_rules(rules,inputs)

            if output_folder_exists:
                output_tables = [
                    os.path.splitext(os.path.basename(x))[0]
                    for x in coconnect.tools.get_files(f"{output_folder}/{name}",type='tsv')
                ]
                
                expected_outputs = list(filtered_rules['cdm'].keys())
                to_process = list(set(expected_outputs) - set(output_tables))
                
                if len(to_process) == 0:
                    continue

                filtered_rules = coconnect.tools.filter_rules_by_destination_tables(filtered_rules,to_process)
               

            logger.debug(f"New data found!")
            logger.info(f"Creating a new task for processing {path}")
                
                            
            if len(inputs) == 0:
                logger.critical(f"Subfolder contains no .csv files!")
                continue
                    
            tables = list(filtered_rules['cdm'].keys())
            logger.debug(f'inputs: {inputs}')
            logger.info(f'cdm tables: {tables}')
                
  
            _data = copy.deepcopy(data)
            _data['input'] = inputs
            _data['output'] = f"{output_folder}/{name}"
        

            _execute(ctx,
                     data=_data,
                     rules=filtered_rules,
                     clean=clean if (i==0 and njobs==0) else False
            )
            njobs+=1
            
        if tdelta is None:
            break
                
        if njobs>0 or i==0:
            logger.info(f"Refreshing {input_folder} every {tdelta} to look for new subfolders....")
            if len(subfolders.values()) == 0:
                logger.warning("No subfolders for data dumps yet found...")

        i+=1
        time.sleep(tdelta.total_seconds())

@click.command(help='print all tables in the bclink tables defined in the config file')
@click.option('--drop-na',is_flag=True)
@click.option('--markdown',is_flag=True)
@click.option('--head',type=int,default=None)
@click.argument("tables",nargs=-1)
@click.pass_obj
def print_tables(ctx,drop_na,markdown,head,tables):

    bclink_helpers = ctx['bclink_helpers']
    logger = Logger("print_tables")

    tables_to_print = list(tables)
    if len(tables_to_print) == 0:
        tables_to_print = list(bclink_helpers.table_map.keys())

    tables = [
        table 
        for table_name,table in bclink_helpers.table_map.items()
        if table_name in tables_to_print
    ]

    for table in tables:
        df = bclink_helpers.get_table(table)
        df.set_index(df.columns[0],inplace=True)
        if drop_na:
            df = df.dropna(axis=1,how='all')
        if markdown:
            df = df.to_markdown()

        click.echo(df)

                

@click.command(help='clean (delete all rows) in the bclink tables defined in the config file')
@click.option('--skip-local-folder',help="dont remove the local output folder",is_flag=True)
@click.pass_obj
def clean_tables(ctx,skip_local_folder,data=None):
    bclink_helpers = ctx['bclink_helpers']
    interactive = ctx['interactive']
   
    logger = Logger("clean_tables")


    if data is None:
        data = ctx['data']

    if isinstance(data,dict):
        output_folders = [data['output']]
    else:
        output_folders = [x['output'] for x in data]

    
    if interactive:
        tables = list(bclink_helpers.table_map.values())
        choices = [ (f"{v} ({k})",v) for k,v in bclink_helpers.table_map.items()]

        tables.append(bclink_helpers.global_ids)
        choices.append((f'{bclink_helpers.global_ids} (global_ids)',bclink_helpers.global_ids))
        
        questions = [
            inquirer.Checkbox('clean_tables',
                              message=f"Clean all-rows in which BCLink tables?",
                              choices=choices,
                              default=tables)
        ]
        answers = inquirer.prompt(questions)
        if answers == None:
            os.kill(os.getpid(), signal.SIGINT)

        tables = answers['clean_tables']
        bclink_helpers.clean_tables(tables)
    else:
        bclink_helpers.clean_tables()
   
    if skip_local_folder:
        return

    if interactive:    
        questions = [
            inquirer.Checkbox('output_folders',
                              message=f"Clean the following output folders?",
                              choices=output_folders,
                              default=output_folders)
        ]
        answers = inquirer.prompt(questions)
        if answers == None:
            os.kill(os.getpid(), signal.SIGINT)
        
        output_folders = answers['output_folders']

    for output_folder in output_folders:
        if not os.path.exists(output_folder):
            logger.info(f"No folder to remove at '{output_folder}'")
            continue
            
        if os.path.exists(output_folder) and os.path.isdir(output_folder):
            logger.info(f"removing {output_folder}")
            shutil.rmtree(output_folder)
   

      

@click.command(help='delete data that has been inserted into bclink')
@click.pass_obj
def delete_data(ctx):
    bclink_helpers = ctx['bclink_helpers']
    logger = Logger("delete_data")
    logger.info("deleting data...")

    data = ctx['data']
    input_data = data['input']
    output_data = data['output']
    
    
    folders = coconnect.tools.get_subfolders(output_data)
    
    options = [
        inquirer.Checkbox('folders',
                      message="Which data-dump do you want to remove?",
                      choices=list(folders.values())
            ),
    ]
    selected_folders = inquirer.prompt(options)
    if selected_folders == None:
        os.kill(os.getpid(), signal.SIGINT)
    selected_folders = selected_folders["folders"]

    for selected_folder in selected_folders:
        files = coconnect.tools.get_files(selected_folder,type='tsv')
                
        options = [
            inquirer.Checkbox('files',
                              message="Confirm the removal of the following tsv files.. ",
                              choices=files,
                              default=files
                          ),
        ]
        selected_files = inquirer.prompt(options)
        if selected_files == None:
            os.kill(os.getpid(), signal.SIGINT)
        selected_files = selected_files["files"]

        for f in selected_files:
        
            bclink_helpers.remove_table(f)
    
            click.echo(f"Deleting {f}")
            os.remove(f)
    

@click.command(help='check and drop for duplicates')
@click.pass_obj
def drop_duplicates(ctx):
    bclink_helpers = ctx['bclink_helpers']
    logger = Logger("drop_duplicates")

    retval = {}
    logger.info("printing to see if tables exist")
    for cdm_table,bclink_table in bclink_helpers.table_map.items():
        #dont do this for person table
        #a person with the same sex and date of birth isnt a duplicate
        if cdm_table == "person":
            continue
        logger.info(f"Looking for duplicates in {cdm_table} ({bclink_table})")

        #if the table hasnt been created, skip
        exists = bclink_helpers.check_table_exists(bclink_table)
        if not exists:
            continue
        #find out what the primary key is 
        droped_duplicates = bclink_helpers.drop_duplicates(bclink_table)
        if len(droped_duplicates)>0:
            logger.warning(f"Found and dropped {len(droped_duplicates)} duplicates in {bclink_table}")
            


@click.command(help='check the bclink tables')
@click.pass_obj
def check_tables(ctx):
    bclink_helpers = ctx['bclink_helpers']
    logger = Logger("check_tables")

    retval = {}
    logger.info("printing to see if tables exist")
    for bclink_table in bclink_helpers.table_map.values():
        retval[bclink_table] = bclink_helpers.check_table_exists(bclink_table)
    if bclink_helpers.global_ids:
        retval[bclink_helpers.global_ids] = bclink_helpers.check_table_exists(bclink_helpers.global_ids)

    logger.info(json.dumps(retval,indent=6))
    return retval


@click.command(help='crate new bclink tables')
@click.pass_context
def create_tables(ctx):
    logger = Logger("create_tables")
    bclink_helpers = ctx.obj['bclink_helpers']
    bclink_helpers.create_tables()                

@click.command(help='Run the Extract part of ETL process for CO-CONNECT integrated with BCLink')
@click.pass_context
def extract(ctx):
    logger = Logger("Extract")
    logger.info("doing extract only")
    ctx.obj['steps'] = ['extract']
    ctx.invoke(execute)

@click.command(help='Run the Transform part of ETL process for CO-CONNECT integrated with BCLink')
@click.pass_context
def transform(ctx):
    logger = Logger("Transform")
    logger.info("doing transform only")
    ctx.obj['steps'] = ['transform']
    ctx.invoke(execute)

@click.command(help='Run the Load part of ETL process for CO-CONNECT integrated with BCLink')
@click.pass_context
def load(ctx):
    logger = Logger("Load")
    logger.info("doing load only")
    ctx.obj['steps'] = ['load']
    ctx.invoke(execute)


@click.command(help='Run the full ETL process for CO-CONNECT integrated with BCLink')
@click.option('run_as_daemon','--daemon','-d',help='run the ETL as a daemon process',is_flag=True)
@click.pass_context
def execute(ctx,run_as_daemon):
    logger = Logger("Execute")
    
    if run_as_daemon and daemon is None:
        raise ImportError(f"You are trying to run in daemon mode, "
                          "but the package 'daemon' hasn't been installed. "
                          "pip install python-daemon. \n"
                          "If you are running on a Windows machine, this package is not supported")

    if run_as_daemon and daemon is not None:
        stderr = ctx.obj['log']
        stdout = f'{stderr}.out'
     
        logger.info(f"running as a daemon process, logging to {stderr}")
        pidfile = TimeoutPIDLockFile('etl.pid', -1)
        logger.info(f"process_id in {pidfile}")

        with open(stdout, 'w+') as stdout_handle, open(stderr, 'w+') as stderr_handle:
            d_ctx = daemon.DaemonContext(
                working_directory=os.getcwd(),
                stdout=stdout_handle,
                stderr=stderr_handle,
                pidfile=TimeoutPIDLockFile('etl.pid', -1)
            )
            with d_ctx:
                _process_data(ctx)
    else:
        _process_data(ctx)


def _extract(ctx,data,rules,bclink_helpers):
    if not 'extract' in ctx.obj['steps']:
        return {'data':data}

    logger = Logger("extract")
    logger.info(f"starting extraction processes")

    inputs = data['input']
    if isinstance(inputs,str):
        if not os.path.exists(inputs):
            raise Exception(f"{inputs} is not an existing path")
        if not os.path.isdir(inputs):
             raise Exception(f"{inputs} is not a dir!")
        inputs = coconnect.tools.get_files(inputs)
        if len(inputs) == 0:
            raise Exception(f"No .csv files found in {inputs}")
    
    do_pseudonymise=False
    _pseudonymise = {}
    if 'pseudonymise' in data:
        _pseudonymise = data['pseudonymise']
        do_pseudonymise = True
        if 'do' in _pseudonymise:
            do_pseudonymise = _pseudonymise['do']
    
    if do_pseudonymise:        
        chunksize = 1000
        if 'chunksize' in _pseudonymise:
            chunksize = _pseudonymise['chunksize']

        output = "./pseudonymised_input_data/"
        if 'output' in _pseudonymise:
            output = _pseudonymise['output']

        if 'salt' not in _pseudonymise:
            raise Exception("To use pseudonymise a salt must be provided!")
        salt = _pseudonymise['salt']
                
        logger.info(f"Called do_pseudonymisation on input data {data} ")
        if not isinstance(rules,dict):
            rules = coconnect.tools.load_json(rules)
        person_id_map = coconnect.tools.get_person_ids(rules)

        input_map = {os.path.basename(x):x for x in inputs}

        inputs = []
        for table,person_id in person_id_map.items():
            if table not in input_map:
                logger.warning(f"Could not find table {table} in input_map")
                logger.warning(input_map)
                continue
            fin = input_map[table]

            print (fin)
            
            fout = ctx.invoke(pseudonymise,
                              input=fin,
                              output_folder=output,
                              chunksize=chunksize,
                              salt=salt,
                              person_id=person_id
                          )
            inputs.append(fout)
        
        data.pop('pseudonymise')
        data['input'] = inputs
    

    _dir = data['output']
    f_global_ids = f"{_dir}/existing_global_ids.tsv"
    f_global_ids = bclink_helpers.get_global_ids(f_global_ids)
    
    indexer = bclink_helpers.get_indicies()
    return {
        'indexer':indexer,
        'data':data,
        'existing_global_ids':f_global_ids
    }

def _transform(ctx,rules,inputs,output_folder,indexer,existing_global_ids):
    if not 'transform' in ctx.obj['steps']:
        return 

    logger = Logger("transform")
    logger.info("starting data transform processes")

    if isinstance(inputs,str):
        inputs = [inputs]

    logger.info(f"inputs: {inputs}")
    logger.info(f"output_folder: {output_folder}")
    logger.info(f"indexer: {indexer}")
    logger.info(f"existing_global_ids: {existing_global_ids}")
    

    ctx.invoke(run,
               rules=rules,
               inputs=inputs,
               output_folder=output_folder,
               indexing_conf=indexer,
               person_id_map=existing_global_ids
    ) 

def _load(ctx,output_folder,cdm_tables,global_ids,bclink_helpers):

    if not 'load' in ctx.obj['steps']:
        return 

    logger = Logger("load")
    logger.info("starting loading data processes")

    logger.info("starting loading global ids")
    if global_ids:
        bclink_helpers.load_global_ids(output_folder)
        
    logger.info("starting loading cdm tables")
    bclink_helpers.load_tables(output_folder,cdm_tables)

        
def _execute(ctx,
             rules=None,
             data=None,
             clean=None,
             bclink_helpers=None):
    
    if data == None:
        data = ctx.obj['data']
    if clean == None:
        clean = ctx.obj['clean']
    if rules == None:
        rules = ctx.obj['rules']
    if bclink_helpers == None:
        bclink_helpers = ctx.obj['bclink_helpers']
    
    interactive = ctx.obj['interactive']
    steps = ctx.obj['steps']

    ctx.obj['listen_for_changes'] = all([step in steps for step in ['extract','transform','load']])

    check_and_drop_duplicates = 'drop_duplicates' in steps

    logger = Logger("execute")
    logger.info(f"Executing steps {steps}")
   

    if clean and 'clean' in steps:
        logger.info(f"cleaning existing bclink tables")
        ctx.invoke(clean_tables,data=data)
   

    tables = list(rules['cdm'].keys())
    if interactive and ('extract' in steps or 'transform' in steps):
        choices = []
        #location = f"{output_folder}/{name}"
        for table in tables:
            source_tables = [
                f"{data['input']}/{x}"
                for x in coconnect.tools.get_source_tables_from_rules(rules,table)
            ]
            choices.append((f"{table} ({source_tables})",table))
        questions = [
            inquirer.Checkbox('tables',
                              message=f"Confirm executing ETL for ... ",
                              choices=choices,
                              default=tables
                          )
        ]
        answers = inquirer.prompt(questions)
        if answers == None:
            os.kill(os.getpid(), signal.SIGINT)
        tables = answers['tables']
        if len(tables) == 0:
            logger.info("no tables selected, skipping..")
            return
        rules = coconnect.tools.filter_rules_by_destination_tables(rules,tables)
        logger.info(f'cdm tables: {tables}')
        
    logger.info(f"Executing ETL...")
        
    #call any extracting of data
    #----------------------------------
    extract_data= _extract(ctx,
                           data,
                           rules,
                           bclink_helpers
    ) 
    indexer = extract_data.get('indexer')
    existing_global_ids = extract_data.get('existing_global_ids')
    data = extract_data.get('data')
   
    #----------------------------------

    inputs = data['input']
    output_folder = data['output']
    
    #call transform
    #----------------------------------
    _transform(ctx,
               rules,
               inputs,
               output_folder,
               indexer,
               existing_global_ids
    )
    #----------------------------------       
    #remove this lookup file once done with it
    if existing_global_ids and os.path.exists(existing_global_ids):
        os.remove(existing_global_ids)


    if 'load' not in steps:
        logger.info("done!")
        return

    cdm_tables = coconnect.tools.get_files(output_folder,type='tsv')
    if interactive:
        choices = []
        for x in cdm_tables:
            tab = os.path.splitext(os.path.basename(x))[0]
            bctab = bclink_helpers.get_bclink_table(tab)
            text = f"{x} --> {bctab} ({tab})"
            choices.append((text,x))
        options = [
            inquirer.Checkbox('cdm_tables',
                              message="Choose which CDM tables to load..",
                              choices=choices,
                              default=cdm_tables
                          ),
        ]
        answers = inquirer.prompt(options)
        if answers == None:
            os.kill(os.getpid(), signal.SIGINT)
        tables_to_load = answers['cdm_tables']
        cdm_tables = tables_to_load
        if len(cdm_tables) == 0 :
            logger.info("No tables chosen to be loaded..")
            return
        else:
            logger.info("Chosen to load...")
            logger.warning(cdm_tables)

    cdm_tables = [
        os.path.splitext(os.path.basename(x))[0]
        for x in cdm_tables
    ]
        
    try:
        idx_global_ids = cdm_tables.index('global_ids')
        global_ids = cdm_tables.pop(idx_global_ids)
    except ValueError:
        global_ids = None
    
    #call load
    #----------------------------------        
    _load(ctx,
          output_folder,
          cdm_tables,
          global_ids,
          bclink_helpers
    )

    if check_and_drop_duplicates:
        #final check for duplicates
        logger.info(f"looking for duplicates and deleting any")
        ctx.invoke(drop_duplicates)

    bclink_helpers.print_report()
    logger.info("done!")


def _get_table_map(table_map,destination_tables):
    #if it's not a dict, and is a file, load the json
    if not isinstance(table_map,dict):
        table_map = coconnect.tools.load_json(table_map)

    # loop over all tables from the rules json
    for table_name in destination_tables:
        #if the dest table is not in the mapping, fail
        if table_name not in table_map.keys():
            raise Exception(f"You must give the name of the bclink table for {table_name}")

    #drop any tables that are not mapped (not in the destination_tables)
    table_map = {k:v for k,v in table_map.items() if k in destination_tables}
    return table_map
    
@click.command(help='[for developers] Run the CO-CONNECT ETL manually ')
@click.option('--rules','-r',help='location of the json rules file',required=True)
@click.option('--output-folder','-o',help='location of the output results folder',required=True)
@click.option('--clean',help='clean all the BCLink tables first by removing all existing rows',is_flag=True)
@click.option('--table-map','-t',help='a look up json file that maps between the CDM table and the table name in BCLink',default={})
@click.option('--gui-user',help='name of the bclink gui user',default='data')
@click.option('--user',help='name of the bclink user',default='bclink')
@click.option('--database',help='name of the bclink database',default='bclink')
@click.option('--dry-run',help='peform a dry-run of the bclink uplod',is_flag=True)
@click.argument('inputs',required=True,nargs=-1)
@click.pass_context
def manual(ctx,rules,inputs,output_folder,clean,table_map,gui_user,user,database,dry_run):

    _rules = coconnect.tools.load_json(rules)
    destination_tables = list(_rules['cdm'].keys())
    
    data = {
        'input':list(inputs),
        'output':output_folder
    }

    table_map = _get_table_map(table_map,destination_tables)
    bclink_settings = {
        'user':user,
        'gui_user': gui_user,
        'database':database,
        'dry_run':dry_run,
        'tables':table_map,
    }

    logger = Logger("Manual")
    logger.info(f'Rules: {rules}')
    logger.info(f'Inputs: {data["input"]}')
    logger.info(f'Output: {data["output"]}')
    logger.info(f'Clean Tables: {clean}')
    logger.info(f'Processing {destination_tables}')
    logger.info(f'BCLink settings:')
    logger.info(json.dumps(bclink_settings,indent=6))
    
    bclink_helpers = BCLinkHelpers(**bclink_settings)

    _execute(ctx,rules,data,clean,bclink_helpers)

                

bclink.add_command(print_tables,'print_tables')
bclink.add_command(clean_tables,'clean_tables')
bclink.add_command(delete_data,'delete_data')
bclink.add_command(drop_duplicates,'drop_duplicates')
bclink.add_command(check_tables,'check_tables')
bclink.add_command(create_tables,'create_tables')
bclink.add_command(execute,'execute')
bclink.add_command(extract,'extract')
bclink.add_command(transform,'transform')
bclink.add_command(load,'load')
etl.add_command(manual,'bclink-manual')
etl.add_command(bclink,'bclink')
#etl.add_command(local,'local')


