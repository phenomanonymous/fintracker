import os
from httplib2 import Http
from datetime import datetime
from apiclient import discovery, errors
from oauth2client.file import Storage
from oauth2client import client, tools
import sys
from email.mime.text import MIMEText
import base64
from pprint import pprint
import inspect
from const.CONSTANTS import SHEET_COLS

def get_credentials(app, scopes, app_name):
    # If modifying these scopes, delete your previously saved credentials
    abbreviated_scopes = '-'.join([x.split('/')[-1] for x in scopes.split(',')])
    print("Pulling credentials for: %s" % abbreviated_scopes)
    # dir_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.dirname(inspect.stack()[-1][1]) # inspect.stack returns stack of calls, -1 is first aka original calling script. [1] is the filename
    CREDS_DIR = os.path.join(dir_path, 'creds')
    CLIENT_SECRET_FILE = '%s/%s/%s.client_secret.json' % (CREDS_DIR, app, app)

    credential_dir = '%s/%s' % (CREDS_DIR, app)
    if not os.path.exists(credential_dir):
        print("Making credentials dir at: %s" % credential_dir)
        os.makedirs(credential_dir)
    CREDS_PATH = os.path.join(credential_dir, '%s.%s.credentials.json' % (app, abbreviated_scopes))

    store = Storage(CREDS_PATH)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, scopes)
        flow.user_agent = app_name
        if sys.version_info[0:2] == (2, 6): # if python version == 2.6
            credentials = tools.run(flow, store)
        else:
            credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + CREDS_PATH)
    return credentials


def get_mint_email_verification_code():
    # Setup the Gmail API
    creds = get_credentials(app='mail', scopes='https://www.googleapis.com/auth/gmail.readonly', app_name=None)
    service = discovery.build('gmail', 'v1', http=creds.authorize(Http()))

    # Call the Gmail API
    response = service.users().messages().list(userId='me', q='Verify your Mint account').execute()
    msg_data = response['messages'][0]
    message = service.users().messages().get(userId='me', id=msg_data['id'], format='raw').execute()
    ver_code = message['snippet'].split(': ')[1].split(' ')[0]
    return ver_code

def create_message(sender, to, subject, message_text):
  message = MIMEText(message_text)
  message['to'] = to
  # message['from'] = sender # if this is set, it can lead to gmail authentication issues, and the mail will be flagged as potentially fraudulent
  message['subject'] = subject
  return {'raw': base64.urlsafe_b64encode(message.as_string())}

def send_message(service, user_id, message):
  try:
    message = (service.users().messages().send(userId=user_id, body=message)
               .execute())
    return message
  except errors.HttpError, error:
    print 'An error occurred: %s' % error

def send_email(sender, to, subject, body):
    creds = get_credentials(app='mail', scopes='https://www.googleapis.com/auth/gmail.send', app_name=None)
    service = discovery.build('gmail', 'v1', http=creds.authorize(Http()))

    msg = create_message(sender, to, subject, body)
    user_id = 'me'
    send_message(service, user_id, msg)

def print_findata_values(findata):
    try:
        pprint(findata)
    except Exception, e:
        print("Exception was: %s" % e)

def update_finances_sheet(master_sheet, findata):
    print_findata_values(findata)
    print("Updating finances sheet")
    creds = get_credentials(app='sheets', scopes='https://www.googleapis.com/auth/spreadsheets', app_name='Google Sheets API Python Quickstart')
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?version=v4')
    service = discovery.build('sheets', 'v4', http=creds.authorize(Http()), discoveryServiceUrl=discoveryUrl)

    rangeName = 'Finances!A:N'
    result = service.spreadsheets().values().get(spreadsheetId=master_sheet, range=rangeName).execute()
    sheet = result.get('values', [])

    print("checking for sheet")
    if not sheet:
        print('No data found.')
    else:
        i = len(sheet)

        today = datetime.now().strftime("%-m/%-d/%Y")
        if today == sheet[i-1][0]:
            print("Overwriting today's row with new data")
            i-=1

        values = [
            [
                today,
                findata[SHEET_COLS[0]],
                findata[SHEET_COLS[1]],
                findata[SHEET_COLS[2]],
                findata[SHEET_COLS[3]],
                None,
                findata[SHEET_COLS[4]],
                None,
                findata[SHEET_COLS[5]],
                findata[SHEET_COLS[6]],
                None,
                None,
                findata[SHEET_COLS[7]],
                0,
                None,
                None,
                findata[SHEET_COLS[8]],
                None
            ]
        ]
        body = {u'values':values}
        range_name = 'Finances!A%d' % (i+1) # i has to be +1 because sheets counts from 1, not 0
        result = service.spreadsheets().values().update(spreadsheetId=master_sheet, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

def update_expenses_sheet(master_sheet, categories, transactions):
    print("Updating expenses sheet")
    creds = get_credentials(app='sheets', scopes='https://www.googleapis.com/auth/spreadsheets', app_name='Google Sheets API Python Quickstart')
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?version=v4')
    service = discovery.build('sheets', 'v4', http=creds.authorize(Http()), discoveryServiceUrl=discoveryUrl)
    headers = [ category.title() for category in categories ]
    headers.insert(0, 'Date')
    values = [
            headers
        ]
    body = {u'values':values}
    range_name = 'Expenses!A1'
    result = service.spreadsheets().values().update(spreadsheetId=master_sheet, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

    i=2

    values = []
    for day in transactions:
        row = [transactions[day][cat] for cat in categories]
        row.insert(0, day)
        values.append(row)
    body = {u'values':values}
    range_name = 'Expenses!A%d' % i
    result = service.spreadsheets().values().update(spreadsheetId=master_sheet, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()
    i+=1
