from entities.ftp_server import start_connection_listener
import signal
import sys


if __name__ == "__main__":
    host = '0.0.0.0'
    port = 2121

    def _handle_sigint(signum, frame):
        print('\nShutting down listener')
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    start_connection_listener(host=host, port=port)