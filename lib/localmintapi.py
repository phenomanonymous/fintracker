try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import BytesIO as StringIO  # Python 3

import re
import json
import requests
from datetime import datetime
from getwebdriver import get_mint_page

MINT_ROOT_URL = 'https://mint.intuit.com'
MINT_ACCOUNTS_URL = 'https://accounts.intuit.com'

JSON_HEADER = {'accept': 'application/json'}
IGNORE_FLOAT_REGEX = re.compile(r"[$,%]")

DATE_FIELDS = [
    'addAccountDate',
    'closeDate',
    'fiLastUpdated',
    'lastUpdated',
]

def assert_pd():
    # Common function to check if pd is installed
    if not pd:
        raise ImportError(
            'transactions data requires pandas; '
            'please pip install pandas'
        )

class MintException(Exception):
    pass

class Mint():
    request_id = 42  # magic number? random number?
    token = None
    driver = None

    def __init__(self, email=None, password=None):
        if email and password:
            self.login_and_get_token(email, password)

    @classmethod
    def create(cls, email, password):
        return Mint(email, password)

    @classmethod
    def get_rnd(cls):  # {{{
        return (str(int(time.mktime(datetime.now().timetuple()))) +
                str(random.randrange(999)).zfill(3))

    def close(self):
        """Logs out and quits the current web driver/selenium session."""
        if not self.driver:
            return

        try:
            print("Logging out")
            self.driver.implicitly_wait(1)
            self.driver.find_element_by_id('link-logout').click()
        except:
            pass

        print("Quitting webdriver")
        self.driver.quit()
        self.driver = None

    def request_and_check(self, url, method='get',
                          expected_content_type=None, **kwargs):
        """Performs a request, and checks that the status is OK, and that the
        content-type matches expectations.

        Args:
          url: URL to request
          method: either 'get' or 'post'
          expected_content_type: prefix to match response content-type against
          **kwargs: passed to the request method directly.

        Raises:
          RuntimeError if status_code does not match.
        """
        assert method in ['get', 'post']
        result = self.driver.request(method, url, **kwargs)
        if result.status_code != requests.codes.ok:
            raise RuntimeError('Error requesting %r, status = %d' %
                               (url, result.status_code))
        if expected_content_type is not None:
            content_type = result.headers.get('content-type', '')
            if not re.match(expected_content_type, content_type):
                raise RuntimeError(
                    'Error requesting %r, content type %r does not match %r' %
                    (url, content_type, expected_content_type))
        return result

    def get(self, url, **kwargs):
        return self.driver.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.driver.request('POST', url, **kwargs)

    def login_and_get_token(self, email, password):
        if self.token and self.driver:
            return

        self.driver = get_mint_page(email, password)
        self.token = self.get_token()

    def get_token(self):
        value_json = self.driver.find_element_by_name(
            'javascript-user').get_attribute('value')
        return json.loads(value_json)['token']

    def get_request_id_str(self):
        req_id = self.request_id
        self.request_id += 1
        return str(req_id)

    def get_accounts(self, get_detail=False):  # {{{
        # Issue service request.
        req_id = self.get_request_id_str()

        input = {
            'args': {
                'types': [
                    'BANK',
                    'CREDIT',
                    'INVESTMENT',
                    'LOAN',
                    'MORTGAGE',
                    'OTHER_PROPERTY',
                    'REAL_ESTATE',
                    'VEHICLE',
                    'UNCLASSIFIED'
                ]
            },
            'id': req_id,
            'service': 'MintAccountService',
            'task': 'getAccountsSorted'
            # 'task': 'getAccountsSortedByBalanceDescending'
        }

        data = {'input': json.dumps([input])}
        account_data_url = (
            '{}/bundledServiceController.xevent?legacy=false&token={}'.format(
                MINT_ROOT_URL, self.token))
        response = self.post(
            account_data_url,
            data=data,
            headers=JSON_HEADER
        ).text
        if req_id not in response:
            raise MintException('Could not parse account data: ' + response)

        # Parse the request
        response = json.loads(response)
        accounts = response['response'][req_id]['response']

        for account in accounts:
            convert_account_dates_to_datetime(account)

        if get_detail:
            accounts = self.populate_extended_account_detail(accounts)

        return accounts

    def set_user_property(self, name, value):
        url = (
            '{}/bundledServiceController.xevent?legacy=false&token={}'.format(
                MINT_ROOT_URL, self.token))
        req_id = self.get_request_id_str()
        result = self.post(
            url,
            data={'input': json.dumps([{'args': {'propertyName': name,
                                                 'propertyValue': value},
                                        'service': 'MintUserService',
                                        'task': 'setUserProperty',
                                        'id': req_id}])},
            headers=JSON_HEADER)
        if result.status_code != 200:
            raise MintException('Received HTTP error %d' % result.status_code)
        response = result.text
        if req_id not in response:
            raise MintException(
                'Could not parse response to set_user_property')

    def get_transactions_json(self, include_investment=False,
                              skip_duplicates=False, start_date=None):
        """Returns the raw JSON transaction data as downloaded from Mint.  The JSON
        transaction data includes some additional information missing from the
        CSV data, such as whether the transaction is pending or completed, but
        leaves off the year for current year transactions.

        Warning: In order to reliably include or exclude duplicates, it is
        necessary to change the user account property 'hide_duplicates' to the
        appropriate value.  This affects what is displayed in the web
        interface.  Note that the CSV transactions never exclude duplicates.
        """

        # Warning: This is a global property for the user that we are changing.
        self.set_user_property(
            'hide_duplicates', 'T' if skip_duplicates else 'F')

        # Converts the start date into datetime format - must be mm/dd/yy
        try:
            start_date = datetime.strptime(start_date, '%m/%d/%y')
        except:
            start_date = None
        all_txns = []
        offset = 0
        # Mint only returns some of the transactions at once.  To get all of
        # them, we have to keep asking for more until we reach the end.
        while 1:
            # Specifying accountId=0 causes Mint to return investment
            # transactions as well.  Otherwise they are skipped by
            # default.
            url = (
                MINT_ROOT_URL +
                '/getJsonData.xevent?' +
                'queryNew=&offset={offset}&comparableType=8&' +
                'rnd={rnd}&{query_options}').format(
                    offset=offset,
                    rnd=Mint.get_rnd(),
                    query_options=(
                        'accountId=0&task=transactions' if include_investment
                        else 'task=transactions,txnfilters&filterType=cash'))
            result = self.request_and_check(
                url, headers=JSON_HEADER,
                expected_content_type='text/json|application/json')
            data = json.loads(result.text)
            txns = data['set'][0].get('data', [])
            if not txns:
                break
            if start_date:
                last_dt = json_date_to_datetime(txns[-1]['odate'])
                if last_dt < start_date:
                    keep_txns = [
                        t for t in txns
                        if json_date_to_datetime(t['odate']) >= start_date]
                    all_txns.extend(keep_txns)
                    break
            all_txns.extend(txns)
            offset += len(txns)
        return all_txns

    def get_detailed_transactions(self, include_investment=False,
                                  skip_duplicates=False,
                                  remove_pending=True,
                                  start_date=None):
        """Returns the JSON transaction data as a DataFrame, and converts
        current year dates and prior year dates into consistent datetime
        format, and reverses credit activity.

        Note: start_date must be in format mm/dd/yy. If pulls take too long,
        use a more recent start date. See json explanations of
        include_investment and skip_duplicates.

        Also note: Mint includes pending transactions, however these sometimes
        change dates/amounts after the transactions post. They have been
        removed by default in this pull, but can be included by changing
        remove_pending to False

        """
        assert_pd()

        result = self.get_transactions_json(include_investment,
                                            skip_duplicates, start_date)
        df = pd.DataFrame(result)
        df['odate'] = df['odate'].apply(json_date_to_datetime)

        if remove_pending:
            df = df[~df.isPending]
            df.reset_index(drop=True, inplace=True)

        df.amount = df.apply(reverse_credit_amount, axis=1)

        return df

    def get_transactions_csv(self, include_investment=False):
        """Returns the raw CSV transaction data as downloaded from Mint.

        If include_investment == True, also includes transactions that Mint
        classifies as investment-related.  You may find that the investment
        transaction data is not sufficiently detailed to actually be useful,
        however.
        """

        # Specifying accountId=0 causes Mint to return investment
        # transactions as well.  Otherwise they are skipped by
        # default.
        result = self.request_and_check(
            '{}/transactionDownload.event'.format(MINT_ROOT_URL) +
            ('?accountId=0' if include_investment else ''),
            expected_content_type='text/csv')
        # print(result.content)
        # with open("transactions.csv", 'w') as csvfile:
        #     csvfile.write(result.content)
        return result.content

    def get_net_worth(self, account_data=None):
        if account_data is None:
            account_data = self.get_accounts()

        # account types in this list will be subtracted
        invert = set(['loan', 'loans', 'credit'])
        return sum([
            -a['currentBalance']
            if a['accountType'] in invert else a['currentBalance']
            for a in account_data if a['isActive']
        ])

    def get_transactions(self, include_investment=False):
        """Returns the transaction data as a Pandas DataFrame."""
        assert_pd()
        s = StringIO(self.get_transactions_csv(
            include_investment=include_investment))
        s.seek(0)
        df = pd.read_csv(s, parse_dates=['Date'])
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        df.category = (df.category.str.lower()
                       .replace('uncategorized', pd.np.nan))
        return df


    def get_categories(self):  # {{{
        # Get category metadata.
        req_id = self.get_request_id_str()
        data = {
            'input': json.dumps([{
                'args': {
                    'excludedCategories': [],
                    'sortByPrecedence': False,
                    'categoryTypeFilter': 'FREE'
                },
                'id': req_id,
                'service': 'MintCategoryService',
                'task': 'getCategoryTreeDto2'
            }])
        }

        cat_url = (
            '{}/bundledServiceController.xevent?legacy=false&token={}'.format(
                MINT_ROOT_URL, self.token))
        response = self.post(cat_url, data=data, headers=JSON_HEADER).text
        if req_id not in response:
            raise MintException('Could not parse category data: "' +
                                response + '"')
        response = json.loads(response)
        response = response['response'][req_id]['response']

        # Build category list
        categories = {}
        for category in response['allCategories']:
            categories[category['id']] = category

        return categories

    def get_budgets(self):  # {{{
        # Get categories
        categories = self.get_categories()

        # Issue request for budget utilization
        today = date.today()
        this_month = date(today.year, today.month, 1)
        last_year = this_month - timedelta(days=330)
        this_month = (str(this_month.month).zfill(2) +
                      '/01/' + str(this_month.year))
        last_year = (str(last_year.month).zfill(2) +
                     '/01/' + str(last_year.year))
        url = "{}/getBudget.xevent".format(MINT_ROOT_URL)
        params = {
            'startDate': last_year,
            'endDate': this_month,
            'rnd': Mint.get_rnd(),
        }
        response = json.loads(self.get(url, params, headers=JSON_HEADER)).text

        # Make the skeleton return structure
        budgets = {
            'income': response['data']['income'][
                str(max(map(int, response['data']['income'].keys())))
            ]['bu'],
            'spend': response['data']['spending'][
                str(max(map(int, response['data']['income'].keys())))
            ]['bu']
        }

        # Fill in the return structure
        for direction in budgets.keys():
            for budget in budgets[direction]:
                budget['cat'] = self.get_category_from_id(
                    budget['cat'],
                    categories
                )

        return budgets

    def get_category_from_id(self, cid, categories):
        if cid == 0:
            return 'Uncategorized'

        for i in categories:
            if categories[i]['id'] == cid:
                return categories[i]['name']

            if 'children' in categories[i]:
                for j in categories[i]['children']:
                    if categories[i][j]['id'] == cid:
                        return categories[i][j]['name']

        return 'Unknown'

    def initiate_account_refresh(self):
        self.post(
            '{}/refreshFILogins.xevent'.format(MINT_ROOT_URL),
            data={'token': self.token},
            headers=JSON_HEADER)


def get_accounts(email, password, get_detail=False):
    mint = Mint.create(email, password)
    return mint.get_accounts(get_detail=get_detail)


def get_net_worth(email, password):
    mint = Mint.create(email, password)
    account_data = mint.get_accounts()
    return mint.get_net_worth(account_data)


def make_accounts_presentable(accounts, presentable_format='EXCEL'):
    formatter = {
        'DATE': '%Y-%m-%d',
        'ISO8601': '%Y-%m-%dT%H:%M:%SZ',
        'EXCEL': '%Y-%m-%d %H:%M:%S',
    }[presentable_format]

    for account in accounts:
        for k, v in account.items():
            if isinstance(v, datetime):
                account[k] = v.strftime(formatter)
    return accounts


def print_accounts(accounts):
    print(json.dumps(make_accounts_presentable(accounts), indent=2))


def get_budgets(email, password):
    mint = Mint.create(email, password)
    return mint.get_budgets()


def initiate_account_refresh(email, password):
    mint = Mint.create(email, password)
    return mint.initiate_account_refresh()


def convert_account_dates_to_datetime(account):
    for df in DATE_FIELDS:
        if df in account:
            # Convert from javascript timestamp to unix timestamp
            # http://stackoverflow.com/a/9744811/5026
            try:
                ts = account[df] / 1e3
            except TypeError:
                # returned data is not a number, don't parse
                continue
            account[df + 'InDate'] = datetime.fromtimestamp(ts)


def json_date_to_datetime(dateraw):
    cy = datetime.isocalendar(date.today())[0]
    try:
        newdate = datetime.strptime(dateraw + str(cy), '%b %d%Y')
    except:
        newdate = datetime.strptime(dateraw, '%m/%d/%y')
    return newdate


def reverse_credit_amount(row):
    amount = float(row['amount'][1:].replace(',', ''))
    return amount if row['isDebit'] else -amount


def parse_float(str_number):
    try:
        return float(IGNORE_FLOAT_REGEX.sub(str_number, ''))
    except ValueError:
        return None
