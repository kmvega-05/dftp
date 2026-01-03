# TODO: manejar respuestas multilínea (FTP multiline reply)


class MessageStructure:
    def __init__(self, code: str, message: str, type: str):
        self.code = code
        self.message = message
        self.type = type

class Parser:
    def __init__(self):
        pass

    def parse_data(self, data: str) -> MessageStructure: 
        code = data[:3]
        message = data[4:]
        ans = MessageStructure(code, message, "info")
        RESPONSE_TYPES = {
        '1': 'preliminary',
        '2': 'success',
        '3': 'missing_info',
        '4': 'error',
        '5': 'error'}
        ans.type = RESPONSE_TYPES.get(code[0], 'unknown')
        return ans
    
    def parse_pasv_response(self, message: str):
        """Parses the PASV response to extract IP and port."""
        try:
            start = message.index('(') + 1
            end = message.index(')')
            parts = message[start:end].split(',')
            ip = '.'.join(parts[:4])
            port = (int(parts[4]) << 8) + int(parts[5])
            return ip, port
        except (ValueError, IndexError) as e:
            raise ValueError("Invalid PASV response format") from e