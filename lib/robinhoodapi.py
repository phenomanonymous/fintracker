from Robinhood import Robinhood, exceptions

def get_robinhood_portfolio_value(username, password):
	my_trader = Robinhood()
	try:
		my_trader.login(username=username, password=password)
		portfolio = my_trader.portfolios()
		if portfolio['extended_hours_equity']:
			return float(portfolio['extended_hours_equity'])
		else:
			return float(portfolio['equity'])
	except exceptions.LoginFailed: # This started happening even with valid creds due to robinhood update, expected token response
		return "BADLOGIN"
