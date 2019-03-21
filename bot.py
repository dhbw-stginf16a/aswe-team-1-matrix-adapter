from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_bot_api.mcommand_handler import MCommandHandler

class BottyMcBotface:
    def __init__(self, server, username, password):
        # This is a bit broken. We don't want to hardcode any room, so set this as soon as we get the first message.
        # The bot is talking to that room then
        self.primary_room = None

        self.receive_handler = None
        self.reset_handler = None

        self.bot = MatrixBotAPI(username, password, server.rstrip("/"))

        # Add a regex handler for every message
        msg_handler = MRegexHandler("^(?!\\!).+", self.__msg_callback)
        self.bot.add_handler(msg_handler)
        reset_handler = MCommandHandler("reset", self.__reset_callback)
        self.bot.add_handler(reset_handler)
        preset_handler = MCommandHandler("preset", self.__preset_callback)
        self.bot.add_handler(preset_handler)

        self.bot.start_polling()

    def __set_primary_room(self, room):
        if self.primary_room is None:
            print("Primary room set!")
            print(room) 
            self.primary_room = room

    def __msg_callback(self, room, event):
        self.__set_primary_room(room)

        if self.receive_handler is not None:
            if event["type"] == "m.room.message" and event["content"]["msgtype"] == "m.text":
                self.receive_handler(room, event["sender"], event["content"]["body"])

    def __reset_callback(self, room, event):
        self.__set_primary_room(room)
        print("Reset!")
        if self.reset_handler is not None:
            self.reset_handler(event["sender"], False)

    def __preset_callback(self, room, event):
        self.__set_primary_room(room)
        print("Preference reset!")
        if self.reset_handler is not None:
            self.reset_handler(event["sender"], True)

    def set_reset_handler(self, handler):
        self.reset_handler = handler

    def set_receive_handler(self, handler):
        self.receive_handler = handler

    def send(self, message, handle = None):
        if self.primary_room is None:
            raise Exception("no room set, write a message to set the room")

        if handle is None:
            self.primary_room.send_text("{}".format(message))
        else:
            self.primary_room.send_text("{} {}".format(handle, message))
