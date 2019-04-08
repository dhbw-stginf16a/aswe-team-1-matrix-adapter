#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

import requests

import os

import pprint
pp = pprint.PrettyPrinter(indent=4)

import connexion
from flask_cors import CORS

from prefclient import PrefStore
PS = PrefStore("matrix_adapter", [
    "watson_assistant_version",
    "watson_assistant_url",
    "watson_assistant_workspace_id",
    "watson_assistant_username",
    "watson_assistant_password",

    "matrix_host",
    "matrix_username",
    "matrix_password",

    "watson_tts_url",
    "watson_tts_apikey"
])

from watson_developer_cloud import AssistantV1
WATSON = AssistantV1(
    version = PS.get_pref("watson_assistant_version"),
    username = PS.get_pref("watson_assistant_username"),
    password = PS.get_pref("watson_assistant_password"),
    url = PS.get_pref("watson_assistant_url")
)
print(WATSON)

from watson_developer_cloud import TextToSpeechV1
TTS = TextToSpeechV1(
    url = PS.get_pref("watson_tts_url"),
    iam_apikey = PS.get_pref("watson_tts_apikey")
)
print(TTS)

from bot import BottyMcBotface
MATRIX_BOT = BottyMcBotface(PS.get_pref("matrix_host"), PS.get_pref("matrix_username"), PS.get_pref("matrix_password"))

class CentralNodeConnection:
    def __init__(self, base_url):
        self.base_url = base_url


    def pref_reset(self, user_handle, input_service):
        res = requests.delete("{}/preferences/user/{}#{}".format(self.base_url, user_handle, input_service))
        assert (res.status_code == 200 or res.status_code == 204)

    def user_exists(self, user_handle, input_service):
        res = requests.post("{}/request".format(self.base_url), json = {
            "skill": "preferences",
            "type": "get_user_prefs",
            "payload": { "keys": ["name"] },
            "user_handle": user_handle,
            "input_service": input_service
        })
        assert res.status_code == 200
        if "name" in res.json():
            return True
        else:
            return False
    
    def tts_on(self, user_handle, input_service):
        res = requests.post("{}/request".format(self.base_url), json = {
            "skill": "preferences",
            "type": "get_user_prefs",
            "payload": { "keys": ["tts"] },
            "user_handle": user_handle,
            "input_service": input_service
        })
        assert res.status_code == 200
        json = res.json()
        if "tts" in json:
            if json["tts"] == "True" or json["tts"] == True or json["tts"] == "true":
                return True
            else:
                return False
        else:
            return False

    def skill_request(self, skill, stype, payload, user_handle, input_service):
        print("Skill request: {} {} {} {} {}".format(skill, stype, payload, user_handle, input_service))
        res = requests.post("{}/request".format(self.base_url), json = {
            "skill": skill,
            "type": stype,
            "payload": payload,
            "user_handle": user_handle,
            "input_service": input_service
        })
        assert res.status_code == 200
        return res.json()


CENTRAL_NODE = CentralNodeConnection(os.environ["CENTRAL_NODE_BASE_URL"])

class MatrixAgent:
    def __init__(self, central_node, bot, tts, watson, watson_workspace_id):
        self.central_node = central_node
        self.bot = bot
        self.tts = tts
        self.watson = watson
        self.watson_workspace_id = watson_workspace_id
        self.bot.set_receive_handler(self.new_message)
        self.bot.set_reset_handler(self.reset)
        self.context = dict()

    def reset(self, sender, is_pref):
        if is_pref:
            self.context = dict()
            self.central_node.pref_reset(sender, "matrix")
            self.bot.send("User preferences ({}#matrix) and context reset...".format(sender))
        else:
            self.context = dict()
            self.bot.send("Context reset...")

    def new_message(self, room, sender, content):
        print("New message: {} {} {}".format(room, sender, content))

        # TODO: Optimize
        self.context["is_new_user"] = not self.central_node.user_exists(sender, "matrix")
        self.context["timezone"] = "Europe/Berlin"

        res = self.watson.message(
            workspace_id = self.watson_workspace_id,
            input = {
                "text": content
            },
            context = self.context
        ).get_result()

        self.handle_watson_response(res, sender)


    def handle_watson_response(self, res, sender):
        print("Handle watson response")
        pp.pprint(res)
        self.context = res["context"]

        tts_on = self.central_node.tts_on(sender, "matrix")

        for msg in res["output"]["text"]:
            self.bot.send(msg)
            if tts_on:
                self.tts_message(msg)

        if "actions" in res:
            self.watson_action(res["actions"], sender)
        
    def watson_action(self, actions, sender):
        print("Watson action {}".format(actions))
        for action in actions:
            skill, stype = action["name"].split("/")

            skill_res = self.central_node.skill_request(
                skill,
                stype,
                action["parameters"],
                sender,
                "matrix"
            )

            self.context[action["result_variable"]] = skill_res

        res = self.watson.message(
            workspace_id = self.watson_workspace_id,
            context = self.context
        ).get_result()
    
        self.handle_watson_response(res, sender)
        
    def tts_message(self, msg):
        res = self.tts.synthesize(msg, accept='audio/mpeg', voice="en-US_AllisonVoice").get_result()
        ufile = self.bot.bot.client.api.media_upload(res.content, "audio/mpeg")
        print(ufile)
        self.bot.bot.client.api.send_content(
            self.bot.primary_room.room_id,
            ufile["content_uri"],
            "bot_tts.m4a",
            "m.audio"
        )

    def proactive_message(self, msg):
        print("Proactive message: {}".format(msg))
        
        self.context["info"] = msg
        self.context["timezone"] = "Europe/Berlin"

        res = self.watson.message(
            workspace_id = self.watson_workspace_id,
            context = self.context
        ).get_result()

        self.handle_watson_response(res, msg["payload"]["user"])



MATRIX_AGENT = MatrixAgent(CENTRAL_NODE, MATRIX_BOT, TTS, WATSON, PS.get_pref("watson_assistant_workspace_id"))

app = connexion.App(__name__, specification_dir='openapi/')
app.add_api('openapi.yml')

# Set CORS headers
CORS(app.app)

# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8080 -w app
application = app.app

logger.info('App initialized')

if __name__ == '__main__':
    # run our standalone server
    app.run(port=8080)
