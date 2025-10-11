from core.connection import ControlConnectionManager
from core.data_connection import DataConnectionManager
from core.parser import Parser, MessageStructure
import os
from datetime import datetime

class ClientCommandHandler:
    def __init__(self, connection: ControlConnectionManager, parser: Parser):
        self.conn = connection
        self.parser = parser
        self.data_addr = None
        # history as list of dicts: {"time":..., "command":..., "response":..., "error":bool}
        self.history = []
    
    # Comandos estandar, que no requieren conexion de datos
    def _execute(self, command: str) -> MessageStructure:
        self.conn.send_command(command)
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        self.history.append({
            "time": datetime.utcnow(),
            "command": command,
            "raw": response,
            "parsed": parsed,
            "error": parsed.type in ("error", "unknown")
        })
        return parsed
    
    def _user(self, username: str):
        return self._execute(f"USER {username}")
    
    def _pass(self, password: str):
        return self._execute(f"PASS {password}")

    def _cwd(self, path: str):
        return self._execute(f"CWD {path}")

    def _rein(self):
        return self._execute("REIN")

    def _mkd(self, path: str):
        return self._execute(f"MKD {path}")

    def _pwd(self):
        return self._execute("PWD")

    def _dele(self, path):
        return self._execute(f"DELE {path}")

    def _rmd(self, path):
        return self._execute(f"RMD {path}")
    
    def _syst(self):
        return self._execute("SYST")
    
    def _type(self, mode: str = "A"):
        return self._execute(f"TYPE {mode}")
    
    def _cdup(self):
        return self._execute("CDUP")
    
    def _rnfr(self, filename: str):
        return self._execute(f"RNFR {filename}")
    
    def _rnto(self, filename: str):
        return self._execute(f"RNTO {filename}")
    
    def _stat(self, args: str):
        return self._execute(f"STAT {args}")

    def _quit(self):
        return self._execute("QUIT")
    
    
    # Comandos que requieren conexion de datos
    def _pasv(self):
        parse_result = self._execute("PASV")
        if not parse_result.code.startswith('2'):
            return parse_result
        ip, port = self.parser.parse_pasv_response(parse_result.message)
        self.data_addr = (ip, port)
        return parse_result

    def _list(self, path: str = ""):
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            return None, pasv_response
        ip, port = self.data_addr
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        command = f"LIST {path}".strip()
        self.conn.send_command(command)
        listing = data_conn.receive_list()
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"LIST {path}".strip(),
            "raw": response,
            "parsed": parsed,
            "data": listing,
            "error": parsed.type in ("error", "unknown")
        })
        return listing, parsed
    
    def _nlst(self, path: str = ""):
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            return None, pasv_response
        ip, port = self.data_addr
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        command = f"NLST {path}".strip()
        self.conn.send_command(command)
        listing = data_conn.receive_list()
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"NLST {path}".strip(),
            "raw": response,
            "parsed": parsed,
            "data": listing,
            "error": parsed.type in ("error", "unknown")
        })
        return listing, parsed

    
    def _retr(self, remote_filename: str, local_path: str):
        """
        Descarga un archivo desde el servidor y lo guarda en local_path.
        """
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            return None, pasv_response
        ip, port = self.data_addr
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        self.conn.send_command(f"RETR {remote_filename}")
        data_conn.receive_file(local_path)
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"RETR {remote_filename}",
            "raw": response,
            "parsed": parsed,
            "file": local_path,
            "error": parsed.type in ("error", "unknown")
        })
        return local_path, parsed
    
    def _stor(self, local_path: str, remote_filename: str = None):
        """
        Sube un archivo local al servidor.
        Si remote_filename no se especifica, se usa el mismo nombre del archivo local.
        """
        if remote_filename is None:
            remote_filename = os.path.basename(local_path)
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            return None, pasv_response
        ip, port = self.data_addr
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        self.conn.send_command(f"STOR {remote_filename}")
        data_conn.send_file(local_path)
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"STOR {remote_filename}",
            "raw": response,
            "parsed": parsed,
            "file": local_path,
            "error": parsed.type in ("error", "unknown")
        })
        return remote_filename, parsed

    
    # Otros comandos utiles
    def _noop(self):
        return self._execute("NOOP")

    # Helpers for UI
    def get_history(self):
        """Return a copy of the history list."""
        return list(self.history)

    def clear_history(self):
        self.history.clear()