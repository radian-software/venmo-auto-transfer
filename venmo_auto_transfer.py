#!/usr/bin/env python3

import argparse
import decimal
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
    return decimal.Decimal(personal_account["balance"]) / 100


def get_primary_bank_id(access_token):
    csrf_cookie = NotImplemented
    resp = requests.get(
        "https://account.venmo.com/api/payment-methods",
        cookies={
            "v_id": "null",
            "api_access_token": access_token,
            "_csrf": csrf_cookie,
        },
        headers={
            "User-Agent": user_agent,
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
            "v_id": "null",
            "api_access_token": access_token,
            "_csrf": csrf_cookie,
        },
        json={
            "fundingInstrumentId": bank_id,
            "amount": int(amount * 100),
            "type": "standard",
        },
        headers={
            "User-Agent": user_agent,
            "Csrf-Token": csrf_token,
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
    access_token = os.environ["VENMO_TOKEN"]
    balance = get_current_balance(access_token)
    log(f"current Venmo balance is ${balance:.2f}")
    if args.transfer and balance > 0:
        primary_bank_id = get_primary_bank_id(access_token)
        log(f"primary bank account has ID ${primary_bank_id}")
    sys.exit(0)


if __name__ == "__main__":
    main()
