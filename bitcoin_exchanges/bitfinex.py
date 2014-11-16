import hmac
import json
import time
import requests
from hashlib import sha384
from base64 import b64encode

from moneyed.classes import Money, MultiMoney

from exchange_util import ExchangeABC, create_ticker, ExchangeError, exchange_config


BASE_URL = 'https://api.bitfinex.com'
REQ_TIMEOUT = 10  # seconds


class Bitfinex(ExchangeABC):
    name = 'bitfinex'
    fiatcurrency = 'USD'

    def __init__(self, key, secret):
        super(Bitfinex, self).__init__()
        self.key = key
        self.secret = secret

    def bitfinex_encode(self, msg):
        msg['nonce'] = str(int(time.time() * 1e6))
        msg = b64encode(json.dumps(msg))
        signature = hmac.new(self.secret, msg, sha384).hexdigest()
        return {
            'X-BFX-APIKEY': self.key,
            'X-BFX-PAYLOAD': msg,
            'X-BFX-SIGNATURE': signature
        }

    def bitfinex_request(self, endpoint, params=None):
        params = params or {}
        params['request'] = endpoint
        response = None
        while response is None:
            try:
                response = requests.post(url=BASE_URL + params['request'],
                                         headers=self.bitfinex_encode(params),
                                         timeout=REQ_TIMEOUT)
                if "Nonce is too small." in response:
                    response = None
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                raise ExchangeError('bitfinex', '%s %s while sending to bitfinex %r' % (type(e), str(e), params))
        return response

    def cancel_order(self, order_id):
        params = {'order_id': int(order_id)}
        try:
            resp = self.bitfinex_request('/v1/order/cancel', params).json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex %r' % (type(e), str(e), params))
        if resp and 'id' in resp and resp['id'] == params['order_id']:
            return True
        elif 'message' in resp and resp['message'] == 'Order could not be cancelled.':
            return True
        else:
            return False

    def cancel_orders(self, **kwargs):
        resp = self.bitfinex_request('/v1/order/cancel/all')
        if resp.text == "All orders cancelled":
            return True
        else:
            return False

    def create_order(self, amount, price, otype, typ='exchange limit', bfxexch='all'):

        if otype == 'bid':
            otype = 'buy'
        elif otype == 'ask':
            otype = 'sell'
        else:
            raise Exception('unknown side %r' % otype)

        params = {
            'side': otype,
            'symbol': 'btcusd',
            'amount': "{:0.3f}".format(amount),
            'price': "{:0.3f}".format(price),
            'exchange': bfxexch,
            'type': typ
        }
        try:
            order = self.bitfinex_request('/v1/order/new', params).json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex %r' % (type(e), str(e), params))

        if 'is_live' in order and order['is_live']:
            return str(order['order_id'])
        raise ExchangeError('bitfinex', 'unable to create order %r response was %r' % (params, order))

    def format_book_item(self, item):
        return super(Bitfinex, self).format_book_item((item['price'], item['amount']))

    def unformat_book_item(self, item):
        return {'price': str(item[0]), 'amount': str(item[1])}

    def get_balance(self, btype='total'):
        try:
            data = self.bitfinex_request('/v1/balances').json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_open_orders' % (type(e), str(e)))
        if 'message' in data:
            raise ExchangeError(exchange='bitfinex', message=data['message'])
        relevant = filter(lambda x: x['currency'] in ('usd', 'btc'), data)

        if btype == 'total':
            total = MultiMoney(*map(lambda x: Money(x['amount'], x['currency'].upper()), relevant))
            return total
        elif btype == 'available':
            available = MultiMoney(*map(lambda x: Money(x['available'], x['currency'].upper()), relevant))
            return available
        else:
            total = MultiMoney(*map(lambda x: Money(x['amount'], x['currency'].upper()), relevant))
            available = MultiMoney(*map(lambda x: Money(x['available'], x['currency'].upper()), relevant))
            return total, available

    def get_open_orders(self):
        try:
            return self.bitfinex_request('/v1/orders').json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_open_orders' % (type(e), str(e)))

    def get_order_book(self, pair='btcusd', **kwargs):
        try:
            return requests.get('%s/v1/book/%s' % (BASE_URL, pair),
                                timeout=REQ_TIMEOUT).json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_order_book' % (type(e), str(e)))

    def get_ticker(self, pair='btcusd'):
        try:
            try:
                rawtick = requests.get(BASE_URL + '/v1/pubticker/%s' % pair, timeout=REQ_TIMEOUT).json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                raise ExchangeError('bitfinex', '%s %s while sending get_ticker to bitfinex' % (type(e), str(e)))

            return create_ticker(bid=rawtick['bid'], ask=rawtick['ask'], high=rawtick['high'], low=rawtick['low'],
                                 volume=rawtick['volume'], last=rawtick['last_price'], timestamp=rawtick['timestamp'],
                                 currency='USD')
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_ticker' % (type(e), str(e)))

    def get_transactions(self, limit=None):
        params = {'symbol': 'BTCUSD'}
        try:
            return self.bitfinex_request('/v1/mytrades', params).json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_transactions' % (type(e), str(e)))

    def get_active_positions(self):
        try:
            return self.bitfinex_request('/v1/positions').json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_active_positions' % (type(e), str(e)))

    def get_order_status(self, order_id):
        params = {'order_id': int(order_id)}
        try:
            return self.bitfinex_request('/v1/order/status', params).json()
        except ValueError as e:
            raise ExchangeError('bitfinex', '%s %s while sending to bitfinex get_order_status for %s' % (
                type(e), str(e), str(order_id)))


exchange = Bitfinex(exchange_config['bitfinex']['api_keys']['key'],
                    exchange_config['bitfinex']['api_keys']['secret'])
