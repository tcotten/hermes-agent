#!/usr/bin/env python3
"""Load GatherMinder's Telegram token through Envoy, then exec Hermes.

No Vault credentials or bot token are written to disk or Docker configuration.
Failures intentionally omit exception text, which can contain Telegram tokens.
"""
import json
import os
import re
import sys
import urllib.request
import uuid

VAULT_URL = "http://192.168.50.104:10000/v1/secret/data/services/hermes-community/telegram"

# Telegram requires bot usernames to end in "bot" (BotFather appends it if
# the requested name doesn't), so the registered username is "GatherMinderBot",
# not the bare display name "GatherMinder". A single source of truth here
# means a future rename in BotFather is a one-line change.
EXPECTED_USERNAME = "gatherminderbot"


def load_token():
    req = urllib.request.Request(VAULT_URL, headers={
        "Host": "vault", "x-requester": "hermes-community",
        "x-intent": "load-community-telegram", "x-data-class": "secret",
        "x-audit-id": str(uuid.uuid4()),
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        token = json.load(response)["data"]["data"]["bot_token"].strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ValueError("Invalid token format")
    return token


def main():
    owner = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    if not re.fullmatch(r"[1-9]\d*", owner):
        print("GatherMinder requires exactly one numeric Telegram owner ID.", file=sys.stderr)
        return 1
    try:
        token = load_token()
        with urllib.request.urlopen("https://api.telegram.org/bot" + token + "/getMe", timeout=20) as response:
            result = json.load(response)
        if not result.get("ok") or result["result"].get("username", "").lower() != EXPECTED_USERNAME:
            print("Vault token does not identify @GatherMinder; gateway not started.", file=sys.stderr)
            return 1
    except Exception:
        print("GatherMinder credential verification failed; gateway not started. Check Vault/Envoy and Telegram connectivity.", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["TELEGRAM_BOT_TOKEN"] = token
    env["TELEGRAM_ALLOW_ALL_USERS"] = "false"
    env["GATEWAY_ALLOW_ALL_USERS"] = "false"
    env["TELEGRAM_GROUP_ALLOWED_USERS"] = owner
    print("Verified @GatherMinder; starting owner-restricted Telegram gateway.", flush=True)
    os.execvpe("hermes", ["hermes", "gateway", "run"], env)


if __name__ == "__main__":
    sys.exit(main())
