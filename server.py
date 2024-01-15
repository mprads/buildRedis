from gevent import socket
from gevent.pool import Pool
from gevent.server import StreamServer

from collections import namedtuple
from io import BytesIO
from socket import error as socket_error

class CommandError(Exception): pass
class Disconnect(Exception): pass

Error = namedtuple('Error', ('message'))

class ProtocalHandler(object):
    def handle_request(self, socket_file):
        # Parse request from client
        pass
    
    def write_response(self, socket_file, data):
        # Serialize response data then send to client
        pass

class Server(object):
    def __init__(self, host='127.0.0.1', port=31337, max_clients=64):
        self._pool = Pool(max_clients)
        # Accepts connections on the passed socket and creates a handler for each connection
        self._server = StreamServer(
            (host, port),
            self.connection_handler,
            spawn=self.pool)

        self_protocol = ProtocalHandler()
        self._kv = {}

    def connection_handler(self, conn, address):
        # Change a socket object into a file-like object
        socket_file = conn.makerfile('rwb')

        # Process requests until client disconnects
        while True:
            try:
                data = self._protocol.handle_request(socket_file)
            except Disconnect:
                break

            try: 
                res = self.get_resonse(data)
            except CommandError as err:
                res = Error(err.args[0])

            self._protocol.write_response(socket_file, res)

    def get_resonse(self, data):
        pass

    def run(self):
        self._server.serve_forever()