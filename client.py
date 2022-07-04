import json
import socket

from util import StopThread
from core import TCPObject


class Client(TCPObject):

    def __init__(self, host):
        TCPObject.__init__(self, host, 5553)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.events = []

        self.main_thread = None

        self.last_error = ""
        self.on_connect = None
        self.on_error = None
    
    def set_connect_callback(self, func):
        self.on_connect = func

    def set_error_callback(self, func):
        self.on_error = func

    def start(self):
        self.active = True
   
        self.main_thread = StopThread(target=self.loop)
        self.main_thread.start()

        return True

    def on(self, channel, func):
        self.events.append((channel, func))

    def off(self, channel):
        self.events = [e for e in self.events if e[0] != channel]

    def loop(self):
        try:
            self.socket.connect((self.host, self.port))
            if self.on_connect:
                self.on_connect()
        except Exception as e:
            self.active = False
            self.last_error = str(e)
            if self.on_error:
                self.on_error()
            return False

        packets = []
        while self.active:
            rcv = self.recieve()
            if rcv == -1:
                self.last_error = "Connection closed"
                break
            else:
                rcv = bytearray(rcv).decode("utf-8")

                for char in rcv:
                    if len(packets) != 0 and packets[-1][-1] != self.end_pkg:
                        packets[-1] += char
                    else:
                        packets.append(char)

                for i, data in enumerate(packets):
                    if data[-1] == self.end_pkg:
                        data = data[:-1]

                        channel = data.split(':')

                        if len(channel) >= 1:
                            channel_name = channel[0]
                            content = ":".join(channel[1:]) if len(channel) >= 2 else ""

                            try:
                                content = json.JSONDecoder().decode(content)
                                
                                for channel, func in self.events:
                                    if channel == channel_name:
                                        func(content)
                            except:
                                pass

                        del packets[i]
        self.close()

    def recieve(self):
        try:
            return self.socket.recv(self.buffer_size)
        except Exception as e:
            self.last_error = str(e)
            return -1

    def send(self,channel, data):
        if self.active:
            try:
                data = json.JSONEncoder().encode(data)
                self.socket.send("{0}:{1}{2}".format(channel,data, self.end_pkg).encode("utf-8"))
                return True
            except Exception as e:
                self.last_error = str(e)
        return False
        

    def close(self):
        self.active = False
        self.last_error = ""
        try:
            self.socket.close()
            return True
        except Exception as e:
            return False

