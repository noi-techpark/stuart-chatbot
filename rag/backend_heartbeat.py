# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import json
import time
from datetime import datetime
import requests


def log(msg: str):
    print(str(datetime.now()) + " " + msg)


# --- load configuration ---

try:
    file = open("backend.json", "r")
    parameters = json.load(file)
    file.close()
except FileNotFoundError:
    print("ERROR: cannot read configuration file.")
    sys.exit(1)

endpoint = parameters["endpoint"]
preshared_secret = parameters["preshared_secret"]

# --- loop to send hearbeat ---

while True:

    connection_timeout = 2.0

    while True:

        try:
            response = requests.get(endpoint + "/heartbeat?secret=" + preshared_secret)
        except requests.exceptions.ConnectionError:
            log("sleep %.0f s after ConnectionError" % connection_timeout)
            time.sleep(connection_timeout)
            if connection_timeout < 32:
                connection_timeout *= 2
            continue

        connection_timeout = 2.0

        time.sleep(2.5)

        continue