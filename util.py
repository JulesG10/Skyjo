import string
import threading


def encode_ip(ip):
    alphabet = string.ascii_lowercase
    code = ""
    for num in ip.split("."):
        num = int(num)
        if num > 25:
            s = str(num)
            for i in range(0, len(s)):
                code += alphabet[int(s[i])]
            code += "-"
        else:
            code += alphabet[num] + "-"

    return code[:-1]


def decode_ip(code):
    alphabet = string.ascii_lowercase
    ip = ""
    
    for charl in code.split("-"):
        for char in charl:
            ip += str(alphabet.index(char))
        ip += "."

    return ip[:-1]


class StopThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()