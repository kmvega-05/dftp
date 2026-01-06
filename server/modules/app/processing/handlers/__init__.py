__all__ = ["handle_noop", "handle_help", "handle_quit", "handle_syst", "handle_user", "handle_pass",
           "handle_rein", "handle_type", "handle_pwd", "handle_cwd", "handle_cdup", "handle_mkd", 
           "handle_rmd", "handle_dele", "handle_rnfr", "handle_rnto", "handle_stat", "handle_pasv",
           "handle_list", "handle_nlst", "handle_retr", "handle_stor"]

def __getattr__(name: str):
    if name == "handle_help":
        from ._help import handle_help
        return handle_help
    if name == "handle_noop":
        from ._noop import handle_noop
        return handle_noop
    if name == "handle_quit":
        from ._quit import handle_quit
        return handle_quit
    if name == "handle_syst":
        from ._syst import handle_syst
        return handle_syst
    if name == "handle_user":
        from ._user import handle_user
        return handle_user
    if name == "handle_pass":
        from ._pass import handle_pass
        return handle_pass
    if name == "handle_rein":
        from ._rein import handle_rein
        return handle_rein
    if name == "handle_type":
        from ._type import handle_type
        return handle_type
    if name == "handle_pwd":
        from ._pwd import handle_pwd
        return handle_pwd
    if name == "handle_cwd":
        from ._cwd import handle_cwd
        return handle_cwd
    if name == "handle_cdup":
        from ._cdup import handle_cdup
        return handle_cdup
    if name == "handle_mkd":
        from ._mkd import handle_mkd
        return handle_mkd
    if name == "handle_rmd":
        from ._rmd import handle_rmd
        return handle_rmd
    if name == "handle_dele":
        from ._dele import handle_dele
        return handle_dele
    if name == "handle_rnfr":
        from ._rnfr import handle_rnfr
        return handle_rnfr
    if name == "handle_rnto":
        from ._rnto import handle_rnto
        return handle_rnto
    if name == "handle_stat":
        from ._stat import handle_stat
        return handle_stat
    if name == "handle_pasv":
        from ._pasv import handle_pasv
        return handle_pasv
    if name == "handle_list":
        from ._list import handle_list
        return handle_list
    if name == "handle_nlst":
        from ._nlst import handle_nlst
        return handle_nlst
    if name == "handle_retr":
        from ._retr import handle_retr
        return handle_retr
    if name == "handle_stor":
        from ._stor import handle_stor
        return handle_stor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return __all__