from gevent import socket
from gevent.pool import Pool
from gevent.server import StreamServer

from collections import namedtuple
from io import BytesIO
from socket import error as socket_error

class CommandError(Exception): pass
class Disconnect(Exception): pass

Error = namedtuple('Error', ('message'))

# The Redis protocol uses a request/response communication pattern with the clients.
# Responses from the server will use the first byte to indicate data-type, followed by the data, terminated by a carriage-return/line-feed.
class ProtocalHandler(object):
    def __init__(self):
        self.handlers = {
            '+': self.handle_simple_string,
            '-': self.handle_error,
            ':': self.handle_integer,
            '$': self.handle_string,
            '*': self.handle_array,
            '%': self.handle_dict
        }

    def handle_request(self, socket_file):
        first_byte = socket_file.read(1)
        
        if not first_byte:
            raise Disconnect()
        
        try:
            return self.handlers[first_byte](socket_file)
        except KeyError:
            raise CommandError('Bad Request')
        
    def handle_simple_string(self, socket_file):
        return socket_file.readline().rstrip('\r\n')

    def handle_error(self, socket_file):
        return Error(socket_file.readline().rstrip('\r\n'))

    def handle_integer(self, socket_file):
        return int(socket_file.readline().rstrip('\r\n'))

    def handle_string(self, socket_file):
        length = int(socket_file.readline().rstrip('\r\n'))
        if length == -1:
            return None  # Special-case for NULLs.
        length += 2  # Include the trailing \r\n in count.
        return socket_file.read(length)[:-2]

    def handle_array(self, socket_file):
        num_elements = int(socket_file.readline().rstrip('\r\n'))
        return [self.handle_request(socket_file) for _ in range(num_elements)]

    def handle_dict(self, socket_file):
        num_items = int(socket_file.readline().rstrip('\r\n'))
        elements = [self.handle_request(socket_file)
                    for _ in range(num_items * 2)]
        return dict(zip(elements[::2], elements[1::2]))
    
    def write_response(self, socket_file, data):
        buffer = BytesIO()
        self._write(buffer, data)
        buffer.seek(0)
        socket_file._write(buffer.getvalue())
        socket_file.flush()

    # Find instance of class and write with the appropriate first byte
    def _write(self, buffer, data):
        if isinstance(data, str):
            data = data.encode('utf-8')

        if isinstance(data, bytes):
            buffer.write('$%s\r\n%s\r\n' % (len(data), data))
        elif isinstance(data, int):
            buffer.write(':%s\r\n' % data)
        elif isinstance(data, Error):
            buffer.write('-%s\r\n' % error.message)
        elif isinstance(data, (list, tuple)):
            buffer.write('*%s\r\n' % len(data))
            for item in data:
                self._write(buffer, item)
        elif isinstance(data, dict):
            buffer.write('%%%s\r\n' % len(data))
            for key in data:
                self._write(buffer, key)
                self._write(buffer, data[key])
        elif data is None:
            buffer.write('$-1\r\n')
        else:
            raise CommandError('unrecognized type: %s' % type(data))

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
        self._commands = self.get_commands()

    def get_commands(self):
        return {
            'GET': self.get,
            'SET': self.set,
            'DELETE': self.delete,
            'FLUSH': self.flush,
            'MGET': self.mget,
            'MSET': self.mset
        }

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

    def get_response(self, data):
        if not isinstance(data, list):
            try:
                data = data.split()
            except:
                raise CommandError('Request must be list or simple string.')

        if not data:
            raise CommandError('Missing command')

        command = data[0].upper()
        if command not in self._commands:
            raise CommandError('Unrecognized command: %s' % command)

        return self._commands[command](*data[1:])

    def get(self, key):
        return self._kv.get(key)

    def set(self, key, value):
        self._kv[key] = value
        return 1

    def delete(self, key):
        if key in self._kv:
            del self._kv[key]
            return 1
        return 0
    
    # I don't get why you store the length before clearing then return that value
    def flush(self):
        kvlen = len(self._kv)
        self._kv.clear()
        return kvlen

    def mget(self, *keys):
        return [self._kv.get(key) for key in keys]

    def mset(self, *items):
        data = zip(items[::2], items[1::2])
        for key, value in data:
            self._kv[key] = value
        return len(data)
    
    def run(self):
        self._server.serve_forever()