#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import json
import hashlib
import hmac
import urllib.request
import urllib.parse
import concurrent.futures
import pandas


class MercadoBitcoinAPI:
    MB_TRANSACTION_API  = 'https://www.mercadobitcoin.net/tapi/v3/'
    MB_TICKER_API       = 'https://www.mercadobitcoin.net/api/{}/ticker'
    MB_STANDARD_REQUEST = dict(
        tapi_method = 'get_account_info',
        tapi_nonce  = 1
    )



    def __init__(self, api_id, api_secret):
        self.api_id=api_id
        self.api_secret=bytes(api_secret, encoding='utf8')



    def make_mb_request_header(self):
        """
        Make the encrypted HTTP request header needed by Mercado Bitcoin API.
        """

        balance_params = urllib.parse.urlencode(self.MB_STANDARD_REQUEST)

        return {
            'user-agent': 'Mozilla',
            'TAPI-ID': self.api_id,
            'TAPI-MAC': (
                hmac
                .new(
                    key       = self.api_secret,
                    digestmod = hashlib.sha512,
                    msg       = '{path}?{query}'.format(
                        path=(
                            urllib.parse.urlparse(
                                self.MB_TRANSACTION_API
                            )
                            .path
                        ),
                        query=balance_params
                    ).encode()
                )
                .hexdigest()
            )
        }


    def get_balances(self):
        """
        Access MercadoBitcoin and returns a Pandas DataFrame with current
        balance of all coins that api_id has balance. Index of DataFrame is the
        coin ticker name.

        Value of balances is in number of coins, not BRL.
        """

        balance_params = urllib.parse.urlencode(self.MB_STANDARD_REQUEST)

        return (
            pandas.DataFrame(
                json.loads(
                    urllib.request.urlopen(
                        urllib.request.Request(
                            url=self.MB_TRANSACTION_API,
                            data=balance_params.encode(),
                            headers=self.make_mb_request_header()
                        )
                    )
                    .read()
                    .decode()
                )
                ['response_data']['balance']
            )
            .T
            .astype(float)
            .query('total>1e-6 or amount_open_orders>1e-6')
        )



    def get_ticker(self,coin):
        """
        Access MercadoBitcoin and returns a dict with current price and status
        of coin.

        Example return for get_ticker('wif'):

        {
            'wif': {
                'buy': '14.16254',
                'date': 1714312974,
                'high': '16.50000000',
                'last': '14.24990000',
                'low': '13.88999999',
                'open': '14.64514645',
                'sell': '14.3492569',
                'vol': '17967.65133008'
            }
        }
        """
        return {
            coin: json.loads(
                urllib.request.urlopen(
                    urllib.request.Request(
                        url=self.MB_TICKER_API.format(coin),
                        headers={'user-agent':'Mozilla'}
                    )
                )
                .read()
                .decode()
            )['ticker']
        }



    def get_BRL_balances(self):
        """
        Uses get_balances() and get_ticker() to build a pandas.DataFrame with
        current BRL balance of all coins that api_id has balance. Index of
        DataFrame is the coin ticker name.

        Example:

        |     |   Total (BRL) |
        |:----|--------------:|
        | brl |     212145.00 |
        | wif |       2354.71 |
        | stx |       1959.41 |
        """
        column_name='Total (BRL)'

        balances=self.get_balances()

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='get_tickers',max_workers=180) as executor:
            tasks=[executor.submit(self.get_ticker,coin) for coin in balances.index.difference(['brl'])]

            # Wait for tasks to finish
            tickers=dict()
            for task in concurrent.futures.as_completed(tasks):
                tickers.update(task.result())

        return (
            balances
            .pipe(
                lambda table: (
                    (
                        table
                        .join(
                            pandas.DataFrame(tickers)
                            .T[['last']]
                            .astype(float)
                        )
                        .assign(**{
                            column_name: lambda table: (
                                (table.total*table['last'])
                                .combine_first(table.total)
                            )
                        })
                    ) if len(tickers.keys())>0
                    else table
                )
            )
            .pipe(
                lambda table: (
                    table.rename(columns=dict(total=column_name))
                    if column_name not in table.columns
                    else table
                )
            )
            [[column_name]]
            .sort_values(column_name,ascending=False)
        )
