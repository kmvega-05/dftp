COMMANDS = [
    "USER",
    "PASS",
    "ACCT",
    "CWD",
    "CDUP",
    "SMNT",
    "QUIT",
    "REIN",
    "PORT",
    "PASV",
    "TYPE",
    "STRU",
    "MODE",
    "RETR",
    "STOR",
    "STOU",
    "APPE",
    "ALLO",
    "REST",
    "RNFR",
    "RNTO",
    "ABOR",
    "DELE",
    "RMD",
    "MKD",
    "PWD",
    "LIST",
    "NLST",
    "SITE",
    "SYST",
    "STAT",
    "HELP",
    "NOOP"
]

def _levenstein(s1: str, s2: str) -> int:
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)
    if s1[0] == s2[0]:
        return _levenstein(s1[1:], s2[1:])
    insert = _levenstein(s1, s2[1:])
    deleted = _levenstein(s1[1:], s2)
    change = _levenstein(s1[1:], s2[1:])
    return 1 + min(insert, deleted, change)

def get_suggestion(cmd: str) -> str:
    dis = float('inf')
    suggestion = ""
    for command in COMMANDS:
        d = _levenstein(cmd.upper(), command)
        if d < dis:
            dis = d
            suggestion = command
    return suggestion if dis <= 3 else ""