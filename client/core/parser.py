# TODO: manejar respuestas multilínea (FTP multiline reply)

import logging

logger = logging.getLogger(__name__)


class MessageStructure:
    def __init__(self, code: str, message: str, type: str):
        self.code = code
        self.message = message
        self.type = type

class Parser:
    def __init__(self):
        pass

    def parse_data(self, data: str) -> MessageStructure: 
        # Ensure data is clean (no leading/trailing whitespace)
        data = data.strip()
        
        # Extract code: must be 3 digits at the start
        code = data[:3]
        
        # Validate that code is actually 3 digits
        if not code.isdigit() or len(code) != 3:
            logger.error(f"Invalid FTP response format: {data} (code={code})")
            return MessageStructure("000", data, "unknown")
        
        # Extract message: everything after code + space (or just after code if no space)
        message = data[4:] if len(data) > 3 and data[3] == ' ' else data[3:]
        
        ans = MessageStructure(code, message, "info")
        RESPONSE_TYPES = {
            '1': 'preliminary',
            '2': 'success',
            '3': 'missing_info',
            '4': 'error',
            '5': 'error'
        }
        ans.type = RESPONSE_TYPES.get(code[0], 'unknown')
        logger.debug(f"Parsed response: code={code}, type={ans.type}, message={message[:50]}")
        return ans
    
    def parse_pasv_response(self, message: str):
        """Parses the PASV response to extract IP and port."""
        try:
            start = message.index('(') + 1
            end = message.index(')')
            parts = message[start:end].split(',')
            ip = '.'.join(parts[:4])
            port = (int(parts[4]) << 8) + int(parts[5])
            logger.debug(f"PASV parsed: {ip}:{port}")
            return ip, port
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse PASV response: {message}")
            raise ValueError("Invalid PASV response format") from e