from core.connection import ControlConnectionManager
from core.data_connection import DataConnectionManager
from core.parser import Parser, MessageStructure
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ClientCommandHandler:
    def __init__(self, connection: ControlConnectionManager, parser: Parser):
        self.conn = connection
        self.parser = parser
        self.data_addr = None
        # history as list of dicts: {"time":..., "command":..., "response":..., "error":bool}
        self.history = []

    def read_banner(self):
        """Read and record the initial banner/welcome message from the server.

        This should be called right after establishing the control connection so the
        UI can show the welcome message immediately (fixes bug #1).
        """
        try:
            logger.info("Reading server banner")
            response = self.conn.receive_response()
            if response:
                parsed = self.parser.parse_data(response)
                logger.info(f"Banner received: {parsed.code} - {parsed.message}")
                self.history.append({
                    "time": datetime.utcnow(),
                    "command": "BANNER",
                    "raw": response,
                    "parsed": parsed,
                    "error": parsed.type in ("error", "unknown")
                })
                return parsed
        except Exception as e:
            logger.warning(f"Failed to read banner: {e}")
            # Don't raise: banner is optional for some servers or may already have been
            # consumed; return None to the caller.
            return None
        return None
    
    # Comandos estandar, que no requieren conexion de datos
    def _execute(self, command: str) -> MessageStructure:
        logger.info(f"Executing command: {command}")
        self.conn.send_command(command)
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        logger.info(f"Response: {parsed.code} - {parsed.message[:50] if parsed.message else ''}")
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
        logger.info(f"LIST operation started for path: '{path}'")
        pasv_response = self._pasv()
        # Store PASV response in history entry later; if PASV failed, return it
        if not pasv_response.code.startswith('2'):
            logger.error(f"PASV failed: {pasv_response.code} - {pasv_response.message}")
            return None, pasv_response
        ip, port = self.data_addr
        logger.debug(f"Data connection established to {ip}:{port}")
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        command = f"LIST {path}".strip()
        # Send the LIST command and expect a preliminary 1xx reply before data
        self.conn.send_command(command)
        # read the preliminary response (usually 1xx) prior to receiving data
        prelim_resp = self.conn.receive_response()
        prelim_parsed = self.parser.parse_data(prelim_resp) if prelim_resp else None
        logger.debug(f"Preliminary response: {prelim_parsed.code if prelim_parsed else 'None'}")
        listing = data_conn.receive_list()
        logger.debug(f"Received listing: {len(listing)} bytes")
        data_conn.close()
        # after data transfer, read final response (2xx/4xx/5xx)
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        logger.info(f"LIST completed: {parsed.code} - {parsed.message}")
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"LIST {path}".strip(),
            # store both prelim and final raw responses when available
            "raw": {
                "pasv": pasv_response.raw if hasattr(pasv_response, 'raw') else str(pasv_response.message) if pasv_response else None,
                "prelim": prelim_resp if prelim_resp else None,
                "final": response
            },
            "parsed": parsed,
            "prelim": prelim_parsed,
            "data": listing,
            "error": parsed.type in ("error", "unknown")
        })
        return listing, parsed
    
    def _nlst(self, path: str = ""):
        logger.info(f"NLST operation started for path: '{path}'")
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            logger.error(f"PASV failed: {pasv_response.code} - {pasv_response.message}")
            return None, pasv_response
        ip, port = self.data_addr
        logger.debug(f"Data connection established to {ip}:{port}")
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        command = f"NLST {path}".strip()
        self.conn.send_command(command)
        prelim_resp = self.conn.receive_response()
        prelim_parsed = self.parser.parse_data(prelim_resp) if prelim_resp else None
        logger.debug(f"Preliminary response: {prelim_parsed.code if prelim_parsed else 'None'}")
        listing = data_conn.receive_list()
        logger.debug(f"Received listing: {len(listing)} bytes")
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        logger.info(f"NLST completed: {parsed.code} - {parsed.message}")
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"NLST {path}".strip(),
            "raw": {
                "pasv": pasv_response.raw if hasattr(pasv_response, 'raw') else str(pasv_response.message) if pasv_response else None,
                "prelim": prelim_resp if prelim_resp else None,
                "final": response
            },
            "parsed": parsed,
            "prelim": prelim_parsed,
            "data": listing,
            "error": parsed.type in ("error", "unknown")
        })
        return listing, parsed

    
    def _retr(self, remote_filename: str, local_path: str):
        """
        Descarga un archivo desde el servidor y lo guarda en local_path.
        """
        logger.info(f"RETR operation started: {remote_filename} → {local_path}")
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            logger.error(f"PASV failed: {pasv_response.code} - {pasv_response.message}")
            return None, pasv_response
        ip, port = self.data_addr
        logger.debug(f"Data connection established to {ip}:{port}")
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        self.conn.send_command(f"RETR {remote_filename}")
        print(remote_filename)
        prelim_resp = self.conn.receive_response()
        prelim_parsed = self.parser.parse_data(prelim_resp) if prelim_resp else None
        logger.debug(f"Preliminary response: {prelim_parsed.code if prelim_parsed else 'None'}")
        data_conn.receive_file(local_path)
        logger.debug(f"File downloaded to {local_path}")
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        logger.info(f"RETR completed: {parsed.code} - {parsed.message}")
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"RETR {remote_filename}",
            "raw": {
                "pasv": pasv_response.raw if hasattr(pasv_response, 'raw') else str(pasv_response.message) if pasv_response else None,
                "prelim": prelim_resp if prelim_resp else None,
                "final": response
            },
            "parsed": parsed,
            "prelim": prelim_parsed,
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
        logger.info(f"STOR operation started: {local_path} → {remote_filename}")
        pasv_response = self._pasv()
        if not pasv_response.code.startswith('2'):
            logger.error(f"PASV failed: {pasv_response.code} - {pasv_response.message}")
            return None, pasv_response
        ip, port = self.data_addr
        logger.debug(f"Data connection established to {ip}:{port}")
        data_conn = DataConnectionManager(ip, port)
        data_conn.connect()
        self.conn.send_command(f"STOR \"{remote_filename}\"")
        print(remote_filename)
        prelim_resp = self.conn.receive_response()
        prelim_parsed = self.parser.parse_data(prelim_resp) if prelim_resp else None
        logger.debug(f"Preliminary response: {prelim_parsed.code if prelim_parsed else 'None'}")
        data_conn.send_file(local_path)
        logger.debug(f"File uploaded from {local_path}")
        data_conn.close()
        response = self.conn.receive_response()
        parsed = self.parser.parse_data(response)
        logger.info(f"STOR completed: {parsed.code} - {parsed.message}")
        self.history.append({
            "time": datetime.utcnow(),
            "command": f"STOR {remote_filename}",
            "raw": {
                "pasv": pasv_response.raw if hasattr(pasv_response, 'raw') else str(pasv_response.message) if pasv_response else None,
                "prelim": prelim_resp if prelim_resp else None,
                "final": response
            },
            "parsed": parsed,
            "prelim": prelim_parsed,
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