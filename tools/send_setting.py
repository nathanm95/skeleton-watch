"""Send settings to Skeleton Watch on a running emulator, as the phone's settings page would.

  ~/.local/share/uv/tools/pebble-tool/bin/python tools/send_setting.py Finish=1 Hands=1 ...

Names are the messageKeys in package.json (ids from build/js/message_keys.json,
so build first); values go as strings, which settings.c accepts. Needs the
pebble-tool Python (it has libpebble2) and one emulator running.
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid

from libpebble2.communication import PebbleConnection
from libpebble2.communication.transports.websocket import WebsocketTransport
from libpebble2.services.appmessage import AppMessageService, CString

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FACE = uuid.UUID(json.load(open(os.path.join(ROOT, "package.json")))["pebble"]["uuid"])
KEYS = json.load(open(os.path.join(ROOT, "build", "js", "message_keys.json")))

ps = subprocess.run(["ps", "ax", "-o", "command"], capture_output=True, text=True).stdout
port = re.search(r"pypkjs .*--port (\d+)", ps)
if not port:
    sys.exit("no emulator running")
pebble = PebbleConnection(WebsocketTransport("ws://localhost:%s/" % port.group(1)))
pebble.connect()
pebble.run_async()
msg = {KEYS[k]: CString(v) for k, v in (a.split("=", 1) for a in sys.argv[1:])}
AppMessageService(pebble).send_message(FACE, msg)
time.sleep(2)
print("sent", ", ".join(sys.argv[1:]))
