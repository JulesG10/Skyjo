import util
import os
import sys
import socket
import random
import keyboard

from server import Server
from client import Client


class Skyjo:
    WIN = 0
    EXIT = 1
    PASS = 2

    NULL_CARD = -10

    def __init__(self):
        self.players: list[list[list[int, bool]]] = []
        self.pass_cards = []
        self.x = 0
        self.y = 0

        self.turn = 0
        self.last_turn = -1

        self.server = None
        self.client = None
        self.active = False

        self.cards_index = 0
        self.cards_data = []
        for i in range(0, 15):
            if i < 5:
                self.cards_data.append(-2)
            if i < 10:
                self.cards_data += range(-1, 12)
            elif i < 15:
                self.cards_data.append(0)
        random.shuffle(self.cards_data)

    def init_game(self):
        self.pass_cards.append(self.get_card())
        self.active = True

        index = 0
        max_val = 0

        for player in self.players:
            for i in range(0, 12):
                player.append([self.get_card(), False])
            player[0][1] = True
            player[1][1] = True

            value = player[0][0] + player[1][0]
            if value > max_val:
                max_val = value
                self.turn = index

            index += 1

    def get_card(self):
        val = self.cards_data[self.cards_index]
        self.cards_index += 1
        if self.cards_index >= len(self.cards_data):
            self.cards_index = 0
        return val

    def card_select(self, player_id, reveal_mode=False):
        self.x = 0
        self.y = 0

        def update(noclear=False):
            msg = []

            player = self.players[player_id]
            for k in range(0, 3):
                line = []
                for i in range(0, 4):
                    pre = ""
                    if i == self.x and k == self.y:
                        pre = ">"

                    card = player[k * 4 + i]
                    if card[0] == Skyjo.NULL_CARD:
                        line.append(pre+"|||")
                    else:
                        if card[1]:
                            line.append(pre+"[{0}]".format(card[0]))
                        else:
                            line.append(pre+"[?]")

                msg.append(" ".join(line))

            for i in range(0, 3):
                if not noclear:
                    sys.stdout.write("\x1b[1A\x1b[2K")
                    sys.stdout.flush()

            print("{0}".format("\n".join(msg)))

        def up():
            self.y -= 1
            if self.y < 0:
                self.y = 0
            update()

        def down():
            self.y += 1
            if self.y >= 3:
                self.y = 2
            update()

        def left():
            self.x -= 1
            if self.x < 0:
                self.x = 0
            update()

        def right():
            self.x += 1
            if self.x >= 4:
                self.x = 3
            update()

        update(True)

        keyboard.add_hotkey('down', down, suppress=True)
        keyboard.add_hotkey('up', up, suppress=True)
        keyboard.add_hotkey('left', left, suppress=True)
        keyboard.add_hotkey('right', right, suppress=True)

        keyboard.wait(hotkey='enter', suppress=True)
        keyboard.clear_all_hotkeys()

        card = self.players[player_id][self.x + 4 * self.y]
        if card[0] == Skyjo.NULL_CARD:
            print("\n-- this card no longer exists ! (retry)\n")
            return self.card_select(player_id)

        if reveal_mode and card[1]:
            print("\n-- this card is already reveal ! (retry)\n")
            return self.card_select(player_id, True)

        print('')
        return (self.x, self.y)

    def add_player(self):
        self.players.append([])
        return len(self.players)-1

    def attach_server(self, server: Server):
        self.server = server

    def attach_client(self, client: Client):
        global wait_play, state, action, info
        wait_play = True
        action = None
        state = "wait_game"
        info = None

        self.client = client
        self.players.append([])

        def on_play(data):
            global state, action
            state = "play"
            action = data

        def on_cards(data):
            global state
            state = "wait_player"
            self.players[0] = data["cards"]

        def on_quit(data):
            global wait_play
            wait_play = False

            print(data["message"])

        def on_update(data):
            global state, info
            info = data
            state = "wait_player"

        def on_win(data):
            global state, info
            state = "win"
            info = data

        self.client.on('player_play', on_play)
        self.client.on('player_update', on_update)
        self.client.on('player_cards', on_cards)
        self.client.on('player_quit', on_quit)
        self.client.on('player_win', on_win)

        self.client.send("player_new", {})

        while wait_play:
            if state == "wait_game":
                print("\rWaiting for game to start...")
                state = None
            elif state == "wait_player":
                if info:
                    print("Waiting for Player #{0} to play\n ----------- Discard card [{1}]".format(
                        info['id'], info['discard'][-1]))
                    if info["last"] == 1:
                        print("Last turn, a player has revealed all his cards !")
                else:
                    print("Waiting for Player #(?) to play")
                state = None
            elif state == "play":
                state = None
                pass_c = action['discard']
                print("\n")
                state = self.action_player(0, pass_c, action['next'])
                if state == Skyjo.EXIT:
                    break

                print("\n")
                self.client.send("player_play", {
                                 "id": action["id"],
                                 "discard": action["discard"],
                                 "cards": self.players[0]
                                 })
            elif state == "win":
                state = None
                if info:
                    print("Player #{0} is the Winner !".format(info['win_id']))
                    for card in self.players[0]:
                        card[1] = True
                    print("\nYour cards:\n")
                    self.show_player_cards(0)
                    print("\nWinner cards:")
                    self.players.append(info['win_cards'])
                    self.show_player_cards(1)
                    break
        self.client.close()

    def loop_play(self):
        if self.server != None:
            global turn_end
            turn_end = False

            if len(self.server.clients) != len(self.players)-1:
                print("Connection error a player is not connected !")
                return

            for i in range(0, len(self.server.clients)):
                try:
                    client, addr = self.server.clients[i]
                    cards = self.players[i]

                    status = self.server.send(
                        "player_cards", {"cards": cards}, client)

                    print("Sending game data to {0}:{1}".format(
                        addr[0], addr[1]))
                    if not status:
                        print("[!] Connection error {0} !".format(
                            self.server.last_error))
                        break
                except:
                    print("[!] Connection error a player is not connected !")
                    break
            print("")

            def on_play(content, client, addr):
                global turn_end
                turn_end = True
                player_id = content["id"]

                try:
                    self.players[player_id] = content["cards"]
                    self.pass_cards = content["discard"]
                except:
                    pass

            def update_data():
                for i in range(0, len(self.server.clients)):
                    if i != self.turn:
                        client, addr = self.server.clients[i]
                        if not self.server.send('player_update', {"discard": self.pass_cards, "id": self.turn, "last": self.last_turn}, client):
                            print("[!] Connection error {0} !".format(
                                self.server.last_error))
                            self.active = False
                            break

            self.server.on('player_play', on_play)

            while self.active:
                if self.turn == len(self.players)-1:
                    state = self.action_player(
                        self.turn, self.pass_cards, self.get_card())
                    if state == Skyjo.WIN:
                        print("Player #{0} Win !".format(self.turn))
                        break
                    elif state == Skyjo.EXIT:
                        total_exit = True
                        print("Player #{0} quit...".format(self.turn))

                        break
                    if self.check_reveal(self.turn):
                        self.last_turn = 0
                        print("Last turn you have reveal all your cards !")
                else:
                    client, _ = self.server.clients[self.turn]
                    turn_end = False
                    self.server.send("player_play", {
                                     "id": self.turn, "next": self.get_card(), "discard": self.pass_cards}, client)
                    while not turn_end:
                        print("\rWaiting for Player #{0} to play...".format(
                            self.turn), end='')

                    if self.check_reveal(self.turn):
                        self.last_turn = 0
                        print("Last turn you have reveal all your cards !")

                self.turn += 1
                self.turn %= len(self.players)
                update_data()

                if self.last_turn != -1:
                    self.last_turn += 1

                if self.last_turn >= len(self.players):
                    self.active = False
                    win_id = self.get_winner()
                    print("\nPlayer #{0} is the Winner !\n".format(win_id))
                    self.show_player_cards(win_id)

                    for i in range(0, len(self.server.clients)):
                        client, addr = self.server.clients[i]
                        if not self.server.send('player_win', {"win_cards": self.players[win_id], "win_id": win_id}, client):
                            print("[!] Connection error {0} !".format(
                                self.server.last_error))
                    break

    def get_winner(self):
        max_val = 0
        best = 0
        index = 0

        for player in self.players:
            sum = 0
            for card in player:
                if card[0] != Skyjo.NULL_CARD:
                    sum += card[0]
            if sum > max_val:
                best = index
            index += 1

        return best

    def check_reveal(self, player_id):
        cards = self.players[player_id]
        for card in cards:
            if not card[1]:
                return False
        return True

    def action_player(self, player_id, pass_cards, next_card):
        print("\n")
        self.show_player_cards(player_id)

        options = ['Take a card from the pile [?]',
                   'Take card [{0}] from the discard pile'.format(
                       pass_cards[-1]),
                   'Exit game']

        index = select("\nPlayer#{0} (action)\t[?] or [{1}]\n".format(
            player_id, pass_cards[-1]), options, "-> {0}")
        replace_card = 0

        if index == 2:
            return Skyjo.EXIT
        elif index == 0:
            replace_card = next_card
            opt = ['Keep', 'Discard']
            if self.check_reveal(player_id):
                opt.pop()

            if select("You got card [{0}] !".format(replace_card), opt, "-> {0}") == 1:
                pass_cards.append(replace_card)
                y, x = self.card_select(player_id, True)
                self.players[player_id][y + 4 * x][1] = True
                print("[?] ------- [{0}]\n".format(pass_cards[-1]))
                self.show_player_cards(player_id)
                return Skyjo.PASS
        elif index == 1:
            replace_card = pass_cards[-1]
            pass_cards.pop()

        y, x = self.card_select(player_id)
        pass_cards.append(self.players[player_id][y + 4 * x][0])
        self.players[player_id][y + 4 * x][1] = True
        self.players[player_id][y + 4 * x][0] = replace_card

        line_count = 0
        for i in range(0, 4):
            same = True
            line = False
            val = Skyjo.NULL_CARD

            for k in range(0, 3):
                card = self.players[player_id][i + 4 * k]
                if not card[1]:
                    same = False
                    break

                if card[0] == Skyjo.NULL_CARD:
                    same = False
                    line = True
                    break
                elif val == Skyjo.NULL_CARD:
                    val = card[0]
                else:
                    if val != card[0]:
                        same = False
                        break
            if same:
                line = True
                for k in range(0, 3):
                    self.players[player_id][i + 4 * k][0] = Skyjo.NULL_CARD
            if line:
                line_count += 1

        if line_count >= 4:
            return Skyjo.WIN

        print("\n[?] ------- [{0}]\n".format(pass_cards[-1]))
        self.show_player_cards(player_id)
        return Skyjo.PASS

    def show_player_cards(self, player_id):
        player = self.players[player_id]
        for k in range(0, 3):
            line = []
            for i in range(0, 4):
                card = player[k * 4 + i]
                if card[0] == Skyjo.NULL_CARD:
                    line.append("|||")
                else:
                    if card[1]:
                        line.append("[{0}]".format(card[0]))
                    else:
                        line.append("[?]")
            print(" ".join(line))
        print('')


def select(title, options, select_style="[{0}]"):
    global index
    index = 0

    print(title)

    def update(noclear=False):
        msg = []
        for i in range(0, len(options)):
            if options[i] == options[index]:
                msg.append(select_style.format(options[i]))
            else:
                msg.append(options[i])

            if not noclear:
                sys.stdout.write("\x1b[1A\x1b[2K")
                sys.stdout.flush()

        print("{0}".format("\n".join(msg)))

    def up():
        global index
        index -= 1
        if index < 0:
            index = len(options)-1
        update()

    def down():
        global index
        index += 1
        if index > len(options)-1:
            index = 0
        update()

    update(True)

    keyboard.add_hotkey('down', down, suppress=True)
    keyboard.add_hotkey('up', up, suppress=True)
    keyboard.wait(hotkey='enter', suppress=True)
    keyboard.clear_all_hotkeys()
    print('')
    return index


def main():
    os.system("title Skyjo")
    logo = """
    █▀▀ █░█ █░░█ ░░▀ █▀▀█ 
    ▀▀█ █▀▄ █▄▄█ ░░█ █░░█ 
    ▀▀▀ ▀░▀ ▄▄▄█ █▄█ ▀▀▀▀ 
    
    
JulesG10 - MIT License 2022 (c)
    """
    print(logo)

    options = ['Create New Game', 'Join Game', 'Exit']
    index = select(
        "Select an option using the up and down keys\n", options, "-> {0}")

    if index == 0:
        global started
        started = False

        ip = socket.gethostbyname(socket.gethostname())
        code = util.encode_ip(ip).upper()

        print("Skyjo Code: {0}".format(code))
        print("(Press [Escape] to start)\n")

        skyjo = Skyjo()
        server = Server()

        server.start()
        skyjo.attach_server(server)

        def new_player(content, client, addr):
            global started
            if not started and len(server.clients)+1 <= 6:
                if len(server.clients)+1 == 6:
                    started = True
                skyjo.add_player()
            else:
                server.send("player_quit", {
                            "message": "The game has already started, try again later !"}, client)

        def start_game():
            global started
            started = True

        def update():
            print("\rThere is {0}/6 players connected... {1}".format(
                len(server.clients)+1, server.last_error), end='')

        server.on("player_new", new_player)
        keyboard.add_hotkey('escape', start_game)

        while not started:
            update()

        keyboard.clear_all_hotkeys()

        print("\nStarting Game ...")
        skyjo.add_player()

        skyjo.init_game()
        skyjo.loop_play()

    elif index == 1:
        global is_connect
        is_connect = False
        code = str(input("Skyjo Code:")).lower()
        ip = util.decode_ip(code)

        skyjo = Skyjo()
        client = Client(ip)

        def connected():
            global is_connect
            is_connect = True
            print("Connection success !")

        def error():
            print("Connection failed")
            print(client.last_error)
            sys.exit(1)

        client.set_connect_callback(connected)
        client.set_error_callback(error)

        client.start()
        while not is_connect:
            pass
        skyjo.attach_client(client)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
