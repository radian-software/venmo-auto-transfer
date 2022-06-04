#!/usr/bin/env python3

import argparse
import os
import sys
import uuid

import dotenv
import requests


def log(msg):
    print(msg, file=sys.stderr)


def fatal(msg):
    log(msg)
    sys.exit(1)


user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36"


def get_current_balance(access_token):
    resp = requests.get(
        "https://account.venmo.com/api/user/identities",
        cookies={
            # If v_id is omitted the request is blocked with a 404, but
            # the value does not seem to be checked. Normally it is a
            # device ID in the form of a UUID with the prefix fp01, but I
            # have decided to ignore that since it does not seem to be a
            # requirement.
            "v_id": "null",
            "api_access_token": access_token,
        },
        # Setting the user agent is not required per se, but the
        # requests library user agent appears to be blocked
        # specifically, so we have to set it to something.
        headers={
            "User-Agent": user_agent,
        },
    )
    assert resp.status_code == 200, resp.status_code
    personal_account = [
        acct for acct in resp.json() if acct["identityType"] == "personal"
    ][0]
    return personal_account["balance"]


def main():
    parser = argparse.ArgumentParser("venmo_auto_transfer")
    parser.add_argument(
        "-t",
        "--transfer",
        action="store_true",
        help="Transfer balance to bank account if nonzero",
    )
    args = parser.parse_args()
    dotenv.load_dotenv()
    access_token = os.environ["VENMO_TOKEN"]
    balance = get_current_balance(access_token)
    log(f"current Venmo balance is ${balance:.2f}")
    if args.transfer and balance > 0:
        log("transferring to linked bank account")
    sys.exit(0)


if __name__ == "__main__":
    main()
