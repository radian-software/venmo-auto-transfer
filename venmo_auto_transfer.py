#!/usr/bin/env python3

import argparse
import os
import sys
import uuid

import dotenv
import requests


user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36"


def log(msg):
    print(msg, file=sys.stderr)


def fatal(msg):
    log(msg)
    sys.exit(1)


def login(username, password):
    device_id = f"fp01-{uuid.uuid4()}"
    resp = requests.post(
        "https://venmo.com/login",
        data={
            "phoneEmailUsername": username,
            "password": password,
            "return_json": "true",
        },
        headers={
            "Cookie": f"v_id={device_id}",
            "User-Agent": user_agent,
        },
    )
    if resp.status_code != 401:
        log(resp.text)
        fatal(f"got unexpected status code {resp.status_code} on /login POST")
    try:
        if resp.json()["error"]["message"] != "Additional authentication is required":
            raise Exception
    except Exception:
        log(resp.text)
        fatal(f"got unexpected response from /login POST")
    otp_secret = resp.headers["venmo-otp-secret"]
    print(otp_secret)


def get_and_print_status(username, password):
    login(username, password)


def main():
    parser = argparse.ArgumentParser("venmo_auto_transfer")
    parser.parse_args()
    dotenv.load_dotenv()
    username = os.environ["VENMO_USERNAME"]
    password = os.environ["VENMO_PASSWORD"]
    get_and_print_status(username, password)
    sys.exit(0)


if __name__ == "__main__":
    main()
