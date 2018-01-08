import requests


class Cryptomkt():
    class ApiError(Exception):
        pass

    API_URL = 'https://api.cryptomkt.com'
    TICKER_ENDPOINT = API_URL + '/v1/ticker'
    MARKET_ENDPOINT = API_URL + '/v1/market'

    def _get_response_data(self, response):
        response = response.json()
        if response['status'] == 'error':
            raise self.ApiError(response['message'])
        return response['data']

    def get_markets(self):
        """Get CryptoMKT market pairs."""
        response = requests.get(self.MARKET_ENDPOINT)
        return self._get_response_data(response)

    def get_tickers(self):
        """Get CryptoMKT tickers."""
        response = requests.get(self.TICKER_ENDPOINT)
        return self._get_response_data(response)
