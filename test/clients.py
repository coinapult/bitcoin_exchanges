from decimal import Decimal
import unittest

from moneyed import Money, MultiMoney

from bitcoin_exchanges.exchange_util import get_live_exchange_workers, Ticker, ExchangeError, OrderbookItem

EXCHANGE = get_live_exchange_workers()


class TestAPI(unittest.TestCase):
    def test_ticker(self):
        for name, mod in EXCHANGE.iteritems():
            print "test_ticker %s" % name
            result = mod.exchange.get_ticker()
            self.assertIsInstance(result, Ticker)

            self.assertIsInstance(result.bid, Money)
            self.assertIsInstance(result.ask, Money)
            self.assertIsInstance(result.high, Money)
            self.assertIsInstance(result.low, Money)
            self.assertIsInstance(result.last, Money)
            self.assertIsInstance(result.volume, Money)
            self.assertEqual(str(result.volume.currency), "BTC")
            self.assertGreater(result.timestamp, 1414170000)

            if name not in ('btcchina', 'kraken'):  # These do not implement the ticker timeout in the same way
                mod.REQ_TIMEOUT = 0.0001
                self.assertRaises(ExchangeError, mod.exchange.get_ticker)
                mod.REQ_TIMEOUT = 10

    def test_get_balance(self):
        for name, mod in EXCHANGE.iteritems():
            print "test_get_balance %s" % name
            total = mod.exchange.get_balance(btype='total')
            self.assertIsInstance(total, MultiMoney)

            avail = mod.exchange.get_balance(btype='available')
            self.assertIsInstance(avail, MultiMoney)

            result = mod.exchange.get_balance(btype='both')
            self.assertIsInstance(result, tuple)
            self.assertIsInstance(result[0], MultiMoney)
            self.assertEqual(result[0], total)
            self.assertIsInstance(result[1], MultiMoney)
            self.assertEqual(result[1], avail)

    def test_create_order(self):
        for name, mod in EXCHANGE.iteritems():
            print "test_create_order %s" % name
            ticker = mod.exchange.get_ticker()
            ask_price = float(ticker.last.amount) * 2
            bal = mod.exchange.get_balance(btype='available')
            if bal.getMoneys(mod.exchange.fiatcurrency) >= Money(1, currency=mod.exchange.fiatcurrency):
                oid = mod.exchange.create_order(amount=1, price=1, otype='bid')
                self.assertIsInstance(oid, str)
            else:
                print "insufficient balance to test create bid order for %s" % name

            self.assertRaises(ExchangeError, mod.exchange.create_order, amount=100000000, price=10,
                              otype='bid')

            if bal.getMoneys('BTC') >= Money(0.01):
                oid = mod.exchange.create_order(amount=0.01, price=ask_price, otype='ask')
                self.assertIsInstance(oid, str)
            else:
                print "insufficient balance to test create ask order for %s" % name

            toomuch = bal.getMoneys('BTC') * 2
            self.assertRaises(ExchangeError, mod.exchange.create_order, amount=float(toomuch.amount), price=ask_price,
                              otype='ask')

    def test_z_cancel_orders(self):
        for name, mod in EXCHANGE.iteritems():
            print "test_z_cancel_orders %s" % name
            resp = mod.exchange.cancel_orders()
            self.assertIsInstance(resp, bool)
            self.assertTrue(resp)

    def test_order_book(self):
        for name, mod in EXCHANGE.iteritems():
            print "test_order_book %s" % name
            raw_book = mod.exchange.get_order_book()

            # check raw book for formatting
            self.assertIn('asks', raw_book)
            self.assertIn('bids', raw_book)
            self.assertGreater(len(raw_book['asks']), 0)
            self.assertGreater(len(raw_book['bids']), 0)

            # check format_book_item
            for i in raw_book['asks']:
                item = mod.exchange.format_book_item(i)
                self.assertIsInstance(item, OrderbookItem)
                self.assertIsInstance(item[0], Decimal)
                self.assertIsInstance(item[1], Decimal)


if __name__ == "__main__":
    unittest.main()
