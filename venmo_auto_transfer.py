#!/usr/bin/env python3

import argparse
import decimal
import json
import os
import re
import sys
import types
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


def get_csrf_data(resp):
    assert resp.status_code == 200, resp.status_code
    csrf_cookie = resp.cookies["_csrf"]
    next_data_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">([^<>]+)</script>',
        resp.text,
    )
    assert next_data_match
    next_data = json.loads(next_data_match.group(1))
    csrf_token = next_data["props"]["pageProps"]["csrfToken"]
    return types.SimpleNamespace(cookie=csrf_cookie, token=csrf_token)


def perform_login(username, password, bank_account_number):
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
    csrf = get_csrf_data(
        requests.get(
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
    )
    resp = requests.post(
        "https://account.venmo.com/api/account/mfa/sign-in",
        cookies={
            "v_id": device_id,
            "_csrf": csrf.cookie,
        },
        headers={
            "csrf-token": csrf.token,
            "xsrf-token": csrf.token,
            "venmo-otp-secret": otp_secret,
            "user-agent": user_agent,
        },
        json={
            "accountNumber": bank_account_number,
        },
    )
    assert resp.status_code == 200, resp.status_code
    access_token = resp.cookies["api_access_token"]
    return access_token


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
    csrf = get_csrf_data(
        requests.get(
            "https://account.venmo.com/cashout",
            cookies={
                "v_id": device_id,
                "api_access_token": access_token,
            },
            headers={
                "user-agent": user_agent,
            },
        )
    )
    resp = requests.get(
        "https://account.venmo.com/api/payment-methods",
        cookies={
            "v_id": device_id,
            "api_access_token": access_token,
            "_csrf": csrf.cookie,
        },
        headers={
            "user-agent": user_agent,
        },
    )
    assert resp.status_code == 200, resp.status_code
    primary_bank = [
        bank
        for bank in resp.json()
        if bank["roles"].get("balanceTransfers") == "primary"
    ][0]
    return primary_bank["value"]


def transfer_balance(access_token, bank_id, amount):
    csrf = get_csrf_data(
        requests.get(
            "https://account.venmo.com/cashout",
            cookies={
                "v_id": device_id,
                "api_access_token": access_token,
            },
            headers={
                "user-agent": user_agent,
            },
        )
    )
    resp = requests.post(
        "https://account.venmo.com/api/transfer",
        cookies={
            "v_id": device_id,
            "api_access_token": access_token,
            "_csrf": csrf.cookie,
        },
        json={
            "fundingInstrumentId": bank_id,
            "amount": int(amount * 100),
            "type": "standard",
        },
        headers={
            "user-agent": user_agent,
            "csrf-token": csrf.token,
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
    access_token = os.environ.get("VENMO_ACCESS_TOKEN")
    if access_token:
        log(f"using existing API access token from .env (not validated)")
    else:
        username = os.environ["VENMO_USERNAME"]
        log(
            f"attempting to login to Venmo as {username} with password and bank account number"
        )
        access_token = perform_login(
            username,
            os.environ["VENMO_PASSWORD"],
            os.environ["VENMO_BANK_ACCOUNT_NUMBER"],
        )
        log(f"obtained new API access token from login")
    balance = get_current_balance(access_token)
    log(f"current Venmo balance is ${balance:.2f}")
    if args.transfer and balance > 0:
        bank_id = get_primary_bank_id(access_token)
        amount = decimal.Decimal("0.01")
        log(f"transferring ${amount:.2f} to primary bank account with ID {bank_id}")
        transfer_balance(access_token, bank_id, amount)
        new_balance = get_current_balance(access_token)
        log(f"success; new balance is ${new_balance:.2f}")
    sys.exit(0)


if __name__ == "__main__":
    main()
