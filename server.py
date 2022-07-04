import socket
import json
from util import encode_ip, StopThread
from core import TCPObject


class Server(TCPObject):


    def __init__(self):
        TCPObject.__init__(self, socket.gethostbyname(socket.gethostname()), 5553)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.code = encode_ip(self.host).upper()
        self.active = False
        
        self.events = []
        
        self.clients = []
        self.clients_threads = []

        self.last_error = ""
        self.main_thread = None

        self.init = False

    def start(self):
        if not self.init:
            try:
                self.socket.bind((self.host, self.port))
                self.socket.listen(5)
            except Exception as e:
                self.last_error = str(e)
                return False
            

        self.active = True
        self.main_thread = StopThread(target=self.loop, daemon=True)
        self.main_thread.start()

        return True

    def on(self, channel, func):
        self.events.append((channel, func))

    def off(self, channel):
        self.events = [e for e in self.events if e[0] != channel]

    def loop(self):
        self.init = True
        while self.active:
            try:
                client, addr = self.socket.accept()
                self.clients.append((client, addr))
                thread = StopThread(target=self.client_loop,args=(client, addr), daemon=True)
                thread.start()
                self.clients_threads.append(thread)
            except Exception:
                break

        self.reset()
        


    def client_loop(self, client, addr):
        packets = []
        while self.active:
            rcv = self.recieve(client)
            if rcv == -1:
                try:
                    for _client in self.clients:
                        if _client[1] == addr:
                            self.clients.remove(_client)
                except:
                    pass

                try:
                    client.close()
                except:
                    pass

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
                                        func(content, client, addr)
                            except:
                                pass
                            
                        del packets[i]
    
    
    def recieve(self, client):
        try:
            return client.recv(self.buffer_size)
        except Exception as e:
            return -1

    def sendall(self, channel, data):
        if self.active:
            try:
                data = json.JSONEncoder().encode(data)
                self.socket.sendall("{0}:{1}{2}".format(channel, data, self.end_pkg).encode("utf-8"))
                return True
            except Exception as e:
                self.last_error = str(e)
                pass
        return False

    def sendaddr(self, channel, data, addr):
        if self.active:
            try:
                data = json.JSONEncoder().encode(data)
                self.socket.sendto("{0}:{1}{2}".format(channel, data, self.end_pkg).encode("utf-8"), addr)
                return True
            except Exception as e:
                self.last_error = str(e)
                for _client in self.clients:
                    if _client[1] == addr:
                        self.clients.remove(_client)
                        break
        return False

    def send(self,channel, data, client):
        if self.active:
            try:
                data = json.JSONEncoder().encode(data)
                client.send("{0}:{1}{2}".format(channel, data, self.end_pkg).encode("utf-8"))
                return True
            except Exception as e:
                self.last_error = str(e)
                for _client in self.clients:
                    if _client[0] == client:
                        self.clients.remove(_client)
                        break
        return False


    def close(self):
        self.active = False
        self.last_error = ""
        self.kill()

    def kill(self):
        self.active = False
        
        for thread in self.clients_threads:
            thread.stop()

        self.clients_threads = []

        if self.main_thread is not None:
            self.main_thread.stop()
        
        # try:
        #     self.socket.shutdown(socket.SHUT_RDWR)
        # except:
        #     pass

        try:
            self.socket.close()
        except:
            pass


    def reset(self):
        
        self.kill()

        self.init = False
        self.clients = []
        self.last_error = ""
            
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

