import shlex

class Command:
    def __init__(self, raw_command):
        self.raw_command = raw_command.strip()
        self.parse_command()
    
    def parse_command(self):
        """Parsea el comando raw en nombre y argumentos, respetando comillas"""
        # Usar shlex para respetar comillas y espacios en argumentos
        parts = shlex.split(self.raw_command)
        if parts:
            self.name = parts[0].upper()  # Comando siempre en mayúsculas
            self.args = parts[1:] if len(parts) > 1 else []
        else:
            self.name = ""
            self.args = []
    
    def __str__(self):
        return f"Command(name='{self.name}', args={self.args})"
    
    def get_name(self):
        """Devuelve el nombre del comando"""
        return self.name
    
    def get_args(self):
        """Devuelve los argumentos del comando"""
        return self.args
    
    def arg_count(self):
        """Devuelve la cantidad de argumentos"""
        return len(self.args)
    
    def require_args(self, count):
        """Verifica si el comando tiene exactamente 'count' argumentos"""
        return self.arg_count() == count
    
    def get_arg(self, index, default=None):
        """Devuelve un argumento específico por índice"""
        try:
            return self.args[index]
        except IndexError:
            return default