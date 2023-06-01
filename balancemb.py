#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import argparse
import logging
import json
import hashlib
import hmac
import urllib.request
import urllib.parse
import concurrent.futures
import smtplib
import email.mime.multipart
import email.mime.text
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
                            data=balance_params.encode('utf-8'),
                            headers={
                                'user-agent': 'Mozilla',
                                'TAPI-ID': self.api_id,
                                'TAPI-MAC': (
                                    hmac
                                    .new(
                                        key       = self.api_secret,
                                        digestmod = hashlib.sha512,
                                        msg       = '{path}?{query}'.format(
                                            path=urllib.parse.urlparse(self.MB_TRANSACTION_API).path,
                                            query=balance_params
                                        ).encode('utf-8')
                                    )
                                    .hexdigest()
                                )
                            }
                        )
                    )
                    .read()
                    .decode('utf-8')
                )['response_data']['balance']
            )
            .T
            .astype(float)
            .query('total>1e-6')
        )

    def get_ticker(self,coin):
        return {
            coin: json.loads(
                urllib.request.urlopen(
                    urllib.request.Request(
                        url=self.MB_TICKER_API.format(coin),
                        headers={'user-agent':'mozilla'}
                    )
                )
                .read()
                .decode('utf-8')
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
            .join(pandas.DataFrame(tickers).T[['last']].astype(float))
            .assign(**{
                column_name: lambda table: (table.total*table['last']).combine_first(table.total)
            })
            [[column_name]]
            .sort_values(ascending=False)
        )


def send_telegram_report(chat_id,bot_id,tokens):
    """
    Send a report via telegram.
    """
    template=[
        'Current balance: <strong>{balance:,.2f} BRL</strong>.',
        'Previous balance: <strong>{balance_prev:,.2f} BRL</strong>.',
        'Variation: <strong>{balance_var:,.2f} BRL</strong>.',
        'Percent change: <strong>{balance_pct_change:,.2%}</strong>.',
        'Brakedown by tokens and coins:',
        '<code>{balances}</code>'
    ]

    message = urllib.parse.quote('\n'.join([line.format(**tokens) for line in template]))

    urllib.request.urlopen(
        urllib.request.Request(
            url=f"https://api.telegram.org/bot{bot_id}/sendMessage?parse_mode=html&chat_id={chat_id}&text={message}",
        )
    )


def send_mail_report(recipient,tokens):
    """
    Use system mailer to send a well formatted e-mail.
    """
    template_subject='Mercado Bitcoin new balance: {balance:,.2f} BRL'
    template_body=[
        '<p>Current balance: <strong>{balance:,.2f} BRL</strong>.</p>',
        '<p>Previous balance: <strong>{balance_prev:,.2f} BRL</strong>.</p>',
        '<p>Variation: <strong>{balance_var:,.2f} BRL</strong>.</p>',
        '<p>Percent change: <strong>{balance_pct_change:,.2%}</strong>.</p>',
        '<p>Brakedown by tokens and coins:</p>',
        '{balances}'
    ]

    msg = email.mime.multipart.MIMEMultipart('mixed')
    body = email.mime.multipart.MIMEMultipart('alternative')

    msg["Subject"]        = template_subject.format(**tokens)
    msg['To']             = recipient
    # msg['In-Reply-To']    = m['original']["Message-ID"]
    # msg['References']     = m['original']["Message-ID"]#+orig["References"].strip()
    msg['Thread-Topic']   = 'Mercado Bitcoin balance'

    body.attach(email.mime.text.MIMEText('\n'.join([line.format(**tokens) for line in template_body]), 'html'))

    msg.attach(body)

    with smtplib.SMTP() as smtp:
        smtp.connect()
        smtp.sendmail('', recipient, msg.as_string())



def prepare_logging(level=logging.INFO):
    # Switch between INFO/DEBUG while running in production/developping:

    # Configure logging for Robson

    FORMATTER = logging.Formatter("%(asctime)s|%(levelname)s|%(name)s|%(message)s")
    HANDLER = logging.StreamHandler()
    HANDLER.setFormatter(FORMATTER)

    loggers=[
        logging.getLogger('__main__'),
        logging.getLogger('urllib'),
        logging.getLogger('pandas')
    ]

    for logger in loggers:
        logger.addHandler(HANDLER)
        logger.setLevel(level)

    return loggers[0]



def prepare_args():
    parser = argparse.ArgumentParser(
        prog='balancemb',
        description='Get consolidated balance from Mercado Bitcoin. Optionaly send it by e-mail and write to CSV file.'
    )

    parser.add_argument(
        '--mb-id',
        dest='MP_API_ID',
        required=True,
        help='API ID as appears at https://www.MercadoBitcoin.com.br/plataforma/chaves-api'
    )

    parser.add_argument(
        '--mb-secret',
        dest='MP_API_SECRET',
        required=True,
        help='Secret string as delivered when an ID was created at https://www.MercadoBitcoin.com.br/plataforma/chaves-api'
    )

    parser.add_argument(
        '--telegram-chat-id',
        dest='TELEGRAM_CHAT_ID',
        required=False,
        default=None,
        help='Recipient’s Telegram ID'
    )

    parser.add_argument(
        '--telegram-bot-id',
        dest='TELEGRAM_BOT_ID',
        required=False,
        default=None,
        help='Telegram bot ID as provided by https://t.me/BotFather'
    )

    parser.add_argument(
        '--csv',
        dest='csv_file_name',
        required=False,
        default=None,
        help='If defined, append consolidated balance to this CSV file'
    )

    parser.add_argument(
        '--csv-fund-name',
        dest='csv_fund_name',
        required=False,
        default='Mercado Bitcoin',
        help='An arbitrary fund name to tag lines in the CSV output'
    )

    parser.add_argument(
        '--treshold',
        dest='balance_variation_treshold',
        required=False,
        type=float,
        default=2,
        help='A minimum BRL value to consider as balance variation'
    )

    parser.add_argument(
        '--mail',
        dest='mail_recipient',
        required=False,
        default=None,
        help='An e-mail address to receive a report.'
    )

    parser.add_argument(
        '--debug',
        dest='DEBUG',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Be more verbose and output messages to console.'
    )

    parsed = parser.parse_args()

    return parsed.__dict__


def main():
    # Read environment and command line parameters
    args=prepare_args()

    # Setup logging
    global logger
    if args['DEBUG']:
        logger=prepare_logging(logging.DEBUG)
        http_handler = urllib.request.HTTPHandler(debuglevel=1)
        try:
          https_handler = urllib.request.HTTPSHandler(debuglevel=1)
          opener = urllib.request.build_opener(http_handler, https_handler)
        except ImportError:
          opener = urllib.request.build_opener(http_handler)
        urllib.request.install_opener(opener)
    else:
        logger=prepare_logging()

    mb=MercadoBitcoinAPI(args['MP_API_ID'],args['MP_API_SECRET'])

    balances=mb.get_BRL_balances()

    balance=pandas.DataFrame(
        data=dict(
            time  = pandas.Timestamp.now(tz='UTC').isoformat(),
            fund  = args['csv_fund_name'],
            BRL   = balances.sum().values[0]
        ),
        index=[0]
    )

    balance_change=None
    balance_prev=None

    if args['csv_file_name']:
        try:
            csv=pandas.read_csv(args['csv_file_name'],sep='|')
        except FileNotFoundError:
            csv=None

        if csv is not None:
            # CSV exists.
            # Append only if balance changed from last position
            # No headers, no index.
            balance_prev=csv.sort_values('time').tail(1).BRL.values[0]
            balance_change=(
                abs(
                    balance.BRL.sum() -
                    balance_prev
                )>args['balance_variation_treshold']
            )

        if csv is not None:
            if balance_change:
                # act if balance change is significant
                # No headers, no index.
                balance.to_csv(
                    args['csv_file_name'],
                    sep='|',
                    index=False,
                    header=False,
                    mode='a',
                )
        else:
            # CSV doesn't exist.
            # Create and write with header
            balance.to_csv(
                args['csv_file_name'],
                sep='|',
                index=False
            )

    if balance_change and args['TELEGRAM_CHAT_ID'] and args['TELEGRAM_BOT_ID']:
        send_telegram_report(
            args['TELEGRAM_CHAT_ID'],
            args['TELEGRAM_BOT_ID'],
            dict(
                balance=balance.BRL.sum(),
                balance_prev=balance_prev,
                balance_var=balance.BRL.sum()-balance_prev,
                balance_pct_change=(balance.BRL.sum()/balance_prev)-1,
                balances=(
                    balances.style
                    .format('{:,.2f} BRL')
                    .to_string()
                )
            )
        )


    if balance_change and args['mail_recipient']:
        send_mail_report(
            args['mail_recipient'],
            dict(
                balance=balance.BRL.sum(),
                balance_prev=balance_prev,
                balance_var=balance.BRL.sum()-balance_prev,
                balance_pct_change=(balance.BRL.sum()/balance_prev)-1,
                balances=(
                    balances.style
                    .format('{:,.2f} BRL')
                    .set_table_styles(
                        [{'selector': 'td',
                          'props': 'text-align: right;'}]
                    )
                    .to_html(border=1)
                )
            )
        )


if __name__ == "__main__":
    main()