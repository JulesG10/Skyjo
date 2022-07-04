

class TCPObject:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.buffer_size = 1024
        self.end_pkg = '\x10'

    def start(self):
        pass

    def recieve(self):
        pass

    def send(self, data):
        pass

    def close(self):
        pass
