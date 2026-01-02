from server.modules.app.processing.handlers import *

# Diccionario de handlers
FTP_COMMAND_HANDLERS = {
    "HELP": handle_help,
    "NOOP": handle_noop,
    "QUIT": handle_quit,
    "SYST": handle_syst,
    "USER": handle_user,
    "PASS": handle_pass,
    "REIN": handle_rein,
    "TYPE": handle_type, 
    "PWD": handle_pwd,  
    "CWD": handle_cwd,
    "CDUP": handle_cdup,
    "MKD": handle_mkd,
    "RMD": handle_rmd,
    "DELE": handle_dele,
    "RNFR": handle_rnfr,
    "RNTO": handle_rnto,
    "STAT": handle_stat,
    "PASV": handle_pasv,
    "LIST": handle_list,
    "NLST": handle_nlst,
    "STOR": handle_stor,
    "RETR": handle_retr
}

