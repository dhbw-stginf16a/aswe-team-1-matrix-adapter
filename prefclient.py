import os, time

import requests
from requests.exceptions import ConnectionError
    
def check_pref(prefs, prefix, pref):
    name = "{}/{}".format(prefix, pref)

    if name in prefs and prefs[name] != "":
        return True
    else:
        print("missing: {}".format(name))
        return False

def check_prefs(prefix, required_prefs, prefs):

    for pref in required_prefs:
        if check_pref(prefs, prefix, pref) != True:
            return False

    return True

class PrefStore:
    def __init__(self, prefix, required_prefs):
        self.prefix = prefix

        while True:
            print("Attempt to fetch preferences")
            try:
                r = requests.get("{}/preferences/global".format(os.environ["CENTRAL_NODE_BASE_URL"]))
                if r.status_code == 200:
                    print("Connection established")
                    if check_prefs(prefix, required_prefs, r.json()):
                        self.p = r.json()
                        print("All required preferences configured")
                        break
            except ConnectionError:
                pass
        
            time.sleep(5)

    def get_pref(self, pref):
        return self.p["{}/{}".format(self.prefix, pref)]
