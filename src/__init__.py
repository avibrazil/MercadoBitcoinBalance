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
    MB_TRANSACTION_API = 'https://www.mercadobitcoin.net/tapi/v3/'
    MB_TICKER_API      = 'https://www.mercadobitcoin.net/api/{}/ticker'

    def __init__(self, api_id, api_secret):
        self.api_id=api_id
        self.api_secret=bytes(api_secret, encoding='utf8')

    def get_balances(self):
        """
        Return a Pandas DataFrame with current balance of all coins that
        api_id has balance. Index of DataFrame is the coin ticker name.

        Value of balances is in number of coins, not BRL.
        """
        balance_params = urllib.parse.urlencode(
            dict(
                tapi_method = 'get_account_info',
                tapi_nonce  = 1
            )
        )

        return (
            pandas.DataFrame(
                json.loads(
                    urllib.request.urlopen(
                        urllib.request.Request(
                            url=self.MB_TRANSACTION_API,
                            data=balance_params.encode(),
                            headers={
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
        Return current price of coin
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
