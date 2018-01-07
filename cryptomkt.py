import requests


class Cryptomkt():
    class ApiError(Exception):
        pass

    API_URL = 'https://api.cryptomkt.com'
    TICKER_ENDPOINT = API_URL + '/v1/ticker'
    MARKET_ENDPOINT = API_URL + '/v1/market'

    def __init__(self, market_code=None):
        self.market_code = market_code

    def set_market(self, market_code):
        self.market_code = market_code

    def _get_response_data(self, response):
        response = response.json()
        if response['status'] == 'error':
            raise self.ApiError(response['message'])
        return response['data']

    def get_markets(self):
        """Get CryptoMKT market pairs."""
        response = requests.get(self.MARKET_ENDPOINT)
        return self._get_response_data(response)

    def get_ticker(self, market_code=None):
        """Get market ticker."""
        market_code = self.market_code or market_code
        if market_code is None:
            raise ValueError("You must specify a market.")
        payload = {'market': market_code}
        response = requests.get(self.TICKER_ENDPOINT, params=payload)
        return self._get_response_data(response)[0]
