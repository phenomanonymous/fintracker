#!/usr/bin/env python

from __future__ import print_function
import atexit
from datetime import date, datetime, timedelta
import random
import sys

from lib.googleapi import update_finances_sheet
from lib.robinhoodapi import get_robinhood_portfolio_value
from lib.localmintapi import Mint, get_accounts, make_accounts_presentable, initiate_account_refresh
from const.CONSTANTS import *
from pprint import pprint

"""
TODO send_gmail WHEN SCRIPT ENCOUNTERS FAILURE/BAD VALUE FOR ACCOUNTS
"""

def main():
    import getpass
    import argparse

    # Parse command-line arguments {{{
    cmdline = argparse.ArgumentParser()
    cmdline.add_argument('email', nargs='?', default=None, help='The e-mail address for your Mint.com account')
    cmdline.add_argument('password', nargs='?', default=None, help='The password for your Mint.com account')

    options = cmdline.parse_args()

    try:  # python 2.x
        from __builtin__ import raw_input as input
    except ImportError:  # python 3
        from builtins import input
    except NameError:
        pass

    # Try to get the e-mail and password from the arguments
    email = options.email
    password = options.password

    if not email:
        # If the user did not provide an e-mail, prompt for it
        if MINT_USER:
            email = MINT_USER
        else:
            email = input("Mint e-mail: ")

    if not password:
        # If we still don't have a password, prompt for it
        if MINT_PASS:
            password = MINT_PASS
        else:
            password = getpass.getpass("Mint password: ")


    print("Creating mint object")
    mint = Mint.create(email, password)
    print("Refreshing mint account details")
    mint.initiate_account_refresh()
    atexit.register(mint.close)  # Ensure everything is torn down.

    try:
        print("Getting accounts data")
        data = make_accounts_presentable(mint.get_accounts(
            get_detail=False)
        )
    except Exception as e:
        print("get_accounts encountered exception: %s" % e)
        data = None

    # output the data
    findata = {}
    for dat in data:
        fintype = "%s: %s" % (dat['fiName'], dat['accountName'])
        findata[fintype] = abs(dat['value'])
    print("Retrieving robinhood portfolio")
    findata[u'Robinhood'] = get_robinhood_portfolio_value(ROBINHOOD_USER, ROBINHOOD_PASS)

    update_finances_sheet(MASTER_SHEET_ID, findata)
    mint.close()

    """ TO-DO: """
    # top-level exception catcher here to close mint no matter what and prevent buildup of zombie instances

if __name__ == '__main__':
    main()
