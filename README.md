# fintracker

automated headless mint screen-scraper, storing data in google sheets

## install.sh

If you are running mac or linux, run ./install.sh to automatically download dependencies

## const dir / Constants.py

You will need to create this file and assign personal variables here such as mint user/pass, sheet IDs, and so on

## creds dir

You will need to create your own google developer app with enabled APIs gmail and sheets, with gmail.readonly scope turned on
You will then need to store the client_secret that gets created in creds/mail and creds/sheets
The script will need to be run once in a GUI environment so that the google auth workflow can launch a browser for the user to sign in and approve the app


## CREDITS

* Credit to mrooney/mintapi for his mintapi python work, I just made a small tweak to make it work on my machine with my workflow, but he did the hard stuff
* Credit to Jamonek/Robinhood for his robinhood api endpoints work
