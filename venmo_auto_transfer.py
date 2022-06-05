#!/usr/bin/env python3

import argparse
import decimal
import json
import os
import re
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
device_id = f"fp01-{uuid.uuid4()}"


def perform_login(username, password):
    resp = requests.post(
        "https://venmo.com/login",
        data={
            "phoneEmailUsername": username,
            "password": password,
            "return_json": "true",
        },
        cookies={
            "v_id": device_id,
        },
        headers={
            "user-agent": user_agent,
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
    resp = requests.get(
        "https://account.venmo.com/account/mfa/verify-bank",
        params={
            "k": otp_secret,
        },
        cookies={
            "v_id": device_id,
        },
        headers={
            "user-agent": user_agent,
        },
    )
    assert resp.status_code == 200, resp.status_code
    csrf_cookie = resp.cookies["_csrf"]
    next_data_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">([^<>]+)</script>',
        resp.text,
    )
    assert next_data_match
    next_data = json.loads(next_data_match.group(1))
    csrf_token = next_data["props"]["pageProps"]["csrfToken"]
    resp = requests.post(
        "https://account.venmo.com/api/account/mfa/sign-in",
        cookies={
            "v_id": device_id,
            "_csrf": csrf_cookie,
        },
        headers={
            "csrf-token": csrf_token,
            "venmo-otp-secret": otp_secret,
        },
    )
    assert resp.status_code == 200, resp.status_code
    return resp.cookies["api_access_token"]


def get_current_balance(access_token):
    resp = requests.get(
        "https://account.venmo.com/api/user/identities",
        cookies={
            "v_id": device_id,
            "api_access_token": access_token,
        },
        # Setting the user agent is not required per se, but the
        # requests library user agent appears to be blocked
        # specifically, so we have to set it to something.
        headers={
            "user-agent": user_agent,
        },
    )
    assert resp.status_code == 200, resp.status_code
    personal_account = [
        acct for acct in resp.json() if acct["identityType"] == "personal"
    ][0]
    return decimal.Decimal(personal_account["balance"]) / 100


def get_primary_bank_id(access_token):
    csrf_cookie = NotImplemented
    resp = requests.get(
        "https://account.venmo.com/api/payment-methods",
        cookies={
            "v_id": device_id,
            "api_access_token": access_token,
            "_csrf": csrf_cookie,
        },
        headers={
            "user-agent": user_agent,
        },
    )
    assert resp.status_code == 200, resp.status_code
    primary_bank = [
        bank for bank in resp.json() if bank["roles"]["balanceTransfers"] == "primary"
    ][0]
    return primary_bank["value"]


def transfer_balance(access_token, amount):
    csrf_cookie = NotImplemented
    csrf_token = NotImplemented
    bank_id = NotImplemented
    resp = requests.post(
        "https://account.venmo.com/api/transfer",
        cookies={
            "v_id": device_id,
            "api_access_token": access_token,
            "_csrf": csrf_cookie,
        },
        json={
            "fundingInstrumentId": bank_id,
            "amount": int(amount * 100),
            "type": "standard",
        },
        headers={
            "user-agent": user_agent,
            "csrf-token": csrf_token,
        },
    )
    assert resp.status_code == 201, resp.status_code


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
    username = os.environ["VENMO_USERNAME"]
    password = os.environ["VENMO_PASSWORD"]
    access_token = perform_login(username, password)
    balance = get_current_balance(access_token)
    log(f"current Venmo balance is ${balance:.2f}")
    if args.transfer and balance > 0:
        primary_bank_id = get_primary_bank_id(access_token)
        log(f"primary bank account has ID ${primary_bank_id}")
    sys.exit(0)


if __name__ == "__main__":
    main()
