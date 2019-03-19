#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

import requests
from requests.exceptions import ConnectionError

import os, time

import pprint
pp = pprint.PrettyPrinter(indent=4)

import connexion
from flask_cors import CORS

p = None

def get_pref(pref):
    return p["matrix_adapter/{}".format(pref)]

def check_pref(prefs, prefix, pref):
    name = "{}/{}".format(prefix, pref)

    if name in prefs and prefs[name] != "":
        return True
    else:
        print("missing: {}".format(name))
        return False

def check_prefs(prefs):
    required_prefs = [
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
    ]

    for pref in required_prefs:
        if check_pref(prefs, "matrix_adapter", pref) != True:
            return False

    return True

while True:
    print("Attempt to fetch preferences")
    try:
        r = requests.get("{}/preferences/global".format(os.environ["CENTRAL_NODE_BASE_URL"]))
        if r.status_code == 200:
            print("Connection established")
            if check_prefs(r.json()):
                p = r.json()
                print("All required preferences configured")
                break
    except ConnectionError:
        pass

    time.sleep(5)



from watson_developer_cloud import AssistantV1
WATSON = AssistantV1(
    version = get_pref("watson_assistant_version"),
    username = get_pref("watson_assistant_username"),
    password = get_pref("watson_assistant_password"),
    url = get_pref("watson_assistant_url")
)
print(WATSON)

from watson_developer_cloud import TextToSpeechV1
TTS = TextToSpeechV1(
    url = get_pref("watson_tts_url"),
    iam_apikey = get_pref("watson_tts_apikey")
)
print(TTS)

from bot import BottyMcBotface
MATRIX_BOT = BottyMcBotface(get_pref("matrix_host"), get_pref("matrix_username"), get_pref("matrix_password"))

class CentralNodeConnection:
    def __init__(self, base_url):
        self.base_url = base_url

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

    def reset(self):
        self.context = dict()

    def new_message(self, room, sender, content):
        print("New message: {} {} {}".format(room, sender, content))

        # TODO: Optimize
        self.context["is_new_user"] = not self.central_node.user_exists(sender, "matrix")

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


MATRIX_AGENT = MatrixAgent(CENTRAL_NODE, MATRIX_BOT, TTS, WATSON, get_pref("watson_assistant_workspace_id"))

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
