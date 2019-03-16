#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

import requests

import pprint
pp = pprint.PrettyPrinter(indent=4)

import connexion
from flask_cors import CORS

CENTRAL_NODE_BASE_URL = "http://localhost:8080/api/v1"
OUR_URL = "http://localhost:8081/api/v1"

from watson_developer_cloud import AssistantV1
WATSON_VERSION = ""
WATSON_HOST = ""
WATSON_WORKSPACE_ID = ""
WATSON_USERNAME = ""
WATSON_PASSWORD = ""
WATSON = AssistantV1(
    version = WATSON_VERSION,
    username = WATSON_USERNAME,
    password = WATSON_PASSWORD,
    url = WATSON_HOST
)

print(WATSON)

from bot import BottyMcBotface, MATRIX_USERNAME, MATRIX_PASSWORD, MATRIX_SERVER
MATRIX_BOT = BottyMcBotface(MATRIX_SERVER, MATRIX_USERNAME, MATRIX_PASSWORD)

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

CENTRAL_NODE = CentralNodeConnection(CENTRAL_NODE_BASE_URL)

class MatrixAgent:
    def __init__(self, central_node, bot, watson, watson_workspace_id):
        self.central_node = central_node
        self.bot = bot
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

        for msg in res["output"]["text"]:
            self.bot.send(msg)

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









MATRIX_AGENT = MatrixAgent(CENTRAL_NODE, MATRIX_BOT, WATSON, WATSON_WORKSPACE_ID)

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
