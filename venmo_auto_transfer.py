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
    print(f"venmo_auto_transfer: {msg}", file=sys.stderr)


def fatal(msg):
    log(msg)
    sys.exit(1)


user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36"
device_id = f"fp01-{uuid.uuid4()}"


def get_next_data(resp):
    assert resp.status_code == 200, resp.status_code
    next_data_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">([^<>]+)</script>',
        resp.text,
    )
    assert next_data_match
    return json.loads(next_data_match.group(1))


def get_csrf_data(resp):
    next_data = get_next_data(resp)
    csrf_cookie = resp.cookies["_csrf"]
    csrf_token = next_data["props"]["pageProps"]["csrfToken"]
    return types.SimpleNamespace(cookie=csrf_cookie, token=csrf_token)


def perform_login(username, password, bank_account_number):
    requests.get("https://venmo.com/account/sign-in", cookies={"v_id": device_id})
    csrf = get_csrf_data(
        requests.get(
            "https://venmo.com/account/sign-in",
            cookies={
                "v_id": device_id,
            },
            headers={
                "user-agent": user_agent,
            },
        )
    )
    resp = requests.post(
        "https://venmo.com/api/login",
        json={
            "username": username,
            "password": password,
            "isGroup": "false",
        },
        cookies={
            "v_id": device_id,
            "_csrf": csrf.cookie,
        },
        headers={
            "csrf-token": csrf.token,
            "xsrf-token": csrf.token,
            "user-agent": user_agent,
        },
    )
    if resp.status_code == 400:
        try:
            if resp.json()["issue"] != "Additional authentication is required":
                raise Exception
        except Exception:
            log(resp.text)
            fatal(f"got unexpected response from /login POST")
        otp_secret = resp.json()["secret"]
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
    elif resp.status_code != 201:
        log(resp.text)
        fatal(f"got unexpected status code {resp.status_code} on /login POST")
    access_token = resp.cookies["api_access_token"]
    return access_token


def get_current_balance(access_token):
    next_data = get_next_data(
        requests.get(
            "https://account.venmo.com/",
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
    )
    return decimal.Decimal(
        next_data["props"]["pageProps"]["initialMobxState"]["profileStore"]["balance"]
    )


def get_primary_bank_id(access_token):
    next_data = get_next_data(
        requests.get(
            "https://account.venmo.com/cashout",
            cookies={
                "api_access_token": access_token,
            },
            # Same as above, we have to set the user agent because
            # requests is blocked.
            headers={
                "user-agent": user_agent,
            },
        )
    )
    primary_bank = [
        bank
        for bank in next_data["props"]["pageProps"]["standardItems"]
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
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print access token",
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
    if args.verbose:
        log(f"access token: {access_token}")
    balance = get_current_balance(access_token)
    log(f"current Venmo balance is ${balance:.2f}")
    if args.transfer:
        if balance > 0:
            bank_id = get_primary_bank_id(access_token)
            amount = balance  # transfer everything
            log(f"transferring ${amount:.2f} to primary bank account with ID {bank_id}")
            transfer_balance(access_token, bank_id, amount)
            new_balance = get_current_balance(access_token)
            log(f"success; new balance is ${new_balance:.2f}")
        if url := os.environ.get("WEBHOOK_URL"):
            log(f"logging success to webhook at {url}")
            requests.get(url)
    sys.exit(0)


if __name__ == "__main__":
    main()
