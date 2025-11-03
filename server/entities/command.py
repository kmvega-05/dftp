import shlex
from typing import Tuple, Optional

class Command:
    """Representa un comando FTP parseado.

    - `raw_command` es la línea recibida (sin CRLF).
    - `name` es el nombre del comando en mayúsculas (str).
    - `args` es una tupla inmutable de argumentos (Tuple[str, ...]).
    """

    def __init__(self, raw_command: str):
        """Crea y parsea el `raw_command`.

        raw_command: cadena tal como llega del socket (puede contener espacios).
        """
        # Normalizar input (quitar CR/LF y espacios alrededor)
        self.raw_command: str = raw_command.strip('\r\n').strip()
        self.name: str = ""
        self.args: Tuple[str, ...] = tuple()
        self._parse_command()

    def _parse_command(self) -> None:
        """Parsea la línea raw en `name` y `args` respetando comillas."""
        if not self.raw_command:
            self.name = ""
            self.args = tuple()
            return
        # shlex.split respeta comillas y escapes
        parts = shlex.split(self.raw_command)
        if not parts:
            self.name = ""
            self.args = tuple()
            return
        self.name = parts[0].upper()
        self.args = tuple(parts[1:])

    def __repr__(self) -> str:
        return f"Command(name={self.name!r}, args={self.args!r})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_name(self) -> str:
        """Devuelve el nombre del comando (en mayúsculas)."""
        return self.name

    def get_args(self) -> Tuple[str, ...]:
        """Devuelve los argumentos como una tupla inmutable."""
        return self.args

    def arg_count(self) -> int:
        """Retorna la cantidad de argumentos."""
        return len(self.args)

    def has_args(self) -> bool:
        """True si el comando tiene al menos un argumento."""
        return self.arg_count() > 0

    def is_empty(self) -> bool:
        """True si la línea de comando estaba vacía o no contiene nombre."""
        return not bool(self.name)

    def require_args(self, count: int) -> bool:
        """Verifica si tiene exactamente `count` argumentos."""
        return self.arg_count() == count

    def get_arg(self, index: int, default: Optional[str] = None) -> Optional[str]:
        """Devuelve el argumento en `index` o `default` si no existe."""
        try:
            return self.args[index]
        except IndexError:
            return default

    def matches(self, name: str) -> bool:
        """True si el nombre del comando coincide con `name` (case-insensitive)."""
        return self.name.upper() == name.upper()

    def to_line(self, include_crlf: bool = True) -> str:
        """Reconstruye la línea del comando (útil para logs o reenvío).

        Si `include_crlf` es True añade '\r\n' al final.
        """
        if not self.name:
            return '\r\n' if include_crlf else ''
        parts = (self.name,) + self.args
        line = ' '.join(parts)
        return (line + '\r\n') if include_crlf else line