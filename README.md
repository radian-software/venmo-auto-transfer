# venmo-auto-transfer

> **As a:** Venmo user
>
> **I want:** No option to automatically deposit payments into my bank
> account
>
> **So that:** I can avoid the complexities of a traditional financial
> institution, such as being FDIC-insured and earning interest

This is a simple application which uses a
[reverse-engineered](https://en.wikipedia.org/wiki/Reverse_engineering)
client for [Venmo](https://venmo.com/) API to automatically deposit
your Venmo balance into your bank account. This option is available
for free within the Venmo app or website at any time, but (unlike with
similar apps) there is no way to set payments to deposit into your
bank account automatically. This is because Venmo makes a profit at
your expense when you leave your money with them, and they have a
business incentive to make it inconvenient to be fiscally responsible.

## Dependencies

This is a pure [Python](https://www.python.org/) application using
[Poetry](https://python-poetry.org/) for dependency management. You
need only have Python 3 and Poetry installed.

## Usage

First you'll need to create a file called `.env` in your local copy of
this repository, with the following contents:

```
VENMO_USERNAME=
VENMO_PASSWORD=
VENMO_BANK_ACCOUNT_NUMBER=
```

You should fill in your Venmo username and password after the equals
signs, and include the account number of your 2FA bank account on the
third line. Note: to find out which bank account is your 2FA bank
account, log in to Venmo in a private browsing window and click
`Confirm another way` on the 2FA screen. Venmo will prompt you with
the name of the bank account it expects.

Now you should be able to invoke `./venmo_auto_transfer.bash` and see
your Venmo balance printed. If there is an issue with authentication
then this command will fail and you will have to debug it. This
application has not been tested with different types of accounts so it
is hard to say whether it will work in general.

If you invoke `./venmo_auto_transfer.bash -t`, then not only will your
balance be printed, but if it is nonzero, then it will be transferred
to whichever linked bank account is marked as the default for bank
transfers (likely the same as your 2FA bank, but not necessarily).

Note that this script is set to work for your PERSONAL Venmo account;
any linked business accounts are ignored.

## Troubleshooting

In order to avoid tripping rate limits related to authentication, the
application has an option to reuse an existing API token that was
generated from a previous login attempt. Note that Venmo API tokens
expire relatively quickly (often within a few hours) and there is no
check for validity within the script, so an expired token will likely
lead to an authentication error (4xx, but not necessarily 401 or 403
like you might expect).

To get the script to print the access token, run it with `-v`. (This
is not done by default for security reasons.) Then, put
`VENMO_ACCESS_TOKEN=` in the `.env` file; the presence of a nonempty
value for this environment variable will override any other
configuration.

## Implementation notes

* Venmo has a very loose relationship with correct use of HTTP status
  codes. The most likely result of omitting a required header or
  setting it to the wrong value is a 403 from CloudFront or nginx (if
  the error is particular egregious, like having a denylisted
  user-agent string) or a 404 (if you fail authentication or something
  similar). The fact that 404s are used for a variety of blocked
  request types is quite annoying.
* Many pages in the Venmo web interface appear to be loaded via
  Next.js and have support for both dynamic loading of additional data
  (à la SPA) as well as loading a server-side rendered page from
  scratch. So depending on what manner you navigate in, data used for
  page rendering might appear in different places. The way that's
  easier to parse is if you load the page from scratch; in that case
  there's a gigantic JSON object in the `__NEXT_DATA__` script tag at
  the bottom of the page which has all the relevant info.
* Venmo uses CSRF tokens extensively. There appear to be two separate
  CSRF tokens you have to submit with many requests: one that is set
  by the server as a cookie, and the other that is provided as part of
  the Next.js configuration in a JSON object in the HTML response (or
  a Next.js async chunk) and must be sent as an HTTP header.
* Marking a client as trusted (so it will not require 2FA again)
  appears to be a rather complex process. It's not just saving a
  cookie client-side; you have to do a GraphQL call to mutate some
  server-side data structure of trusted devices, and there are
  multiple analytics and tracking calls for recording various device
  telemetry which may or may not also be required. This implementation
  avoids the complexity, since there is a 2FA method available that
  does not require the user to be present, and since you have to
  re-login anyway after a few hours to refresh your API token,
  regardless of how trusted your device is. (The mobile app probably
  has a stronger authentication mechanism since you don't have to
  repeatedly sign in to that, but it would also be more of a pain to
  reverse engineer.)
