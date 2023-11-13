#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import argparse
import io
import itertools
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


def send_telegram_report(chat_id,bot_id,tokens):
    """
    Send a report via telegram.
    """

    url_message="https://api.telegram.org/bot{bot_id}/sendMessage?parse_mode=html&chat_id={chat_id}&text={message}"
    url_graph="https://api.telegram.org/bot{bot_id}/sendPhoto"

    template=[
        'Current balance: <strong>{balance:,.2f} BRL</strong>.\n',
        'Previous balance: <strong>{balance_prev:,.2f} BRL</strong>.\n',
        'Variation: <strong>{balance_var:,.2f} BRL</strong>.\n',
        'Percent change: <strong>{balance_pct_change:,.2%}</strong>.\n',
        'Historycal growth: <strong>{balance_growth:,.2%}</strong> in <strong>{balance_growth_period}</strong>.\n',
        '<strong>Brakedown by tokens and coins:</strong>',
        '<pre>{balances}</pre>'
    ]

    message = urllib.parse.quote(
        '\n'.join(
            [
                line.format(**tokens)
                for line in template
            ]
        )
    )

    urllib.request.urlopen(
        urllib.request.Request(
            url=url_message.format(
                bot_id=bot_id,
                chat_id=chat_id,
                message=message
            )
        )
    )

    # with io.BytesIO() as buffer:  # use buffer memory
    #     tokens['balance_history'].plot(kind='line').figure.savefig(buffer, format='png')
    #     buffer.seek(0)

    #     graph = dict(
    #         chat_id=chat_id,
    #         caption='something',
    #         photo=buffer.read()
    #     )

    # urllib.request.urlopen(
    #     urllib.request.Request(
    #         url=url_graph.format(bot_id=bot_id),
    #         data=urllib.parse.urlencode(graph).encode()
    #     )
    # )

    # print(urllib.parse.urlencode(graph).encode()[:200])


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
        '--csv-threshold',
        dest='csv_threshold',
        required=False,
        type=float,
        default=0,
        help='Save updated balance on CSV only if balance variation is bigger than this'
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
        '--report-threshold',
        dest='report_threshold',
        required=False,
        type=float,
        default=2,
        help='Send report only if balance variation is bigger than this'
    )

    parser.add_argument(
        '--mail',
        dest='mail_recipient',
        required=False,
        default=None,
        help='An e-mail address to receive a report.'
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
            fund  = args['csv_fund_name'],
            BRL   = balances.sum().values[0]
        ),
        index=pandas.DatetimeIndex([pandas.Timestamp.now(tz='UTC')], name='time')
    )

    balance_change_for_report=True
    balance_change_for_csv=True
    balance_prev=None
    csv=None

    if args['csv_file_name']:
        try:
            csv=pandas.read_csv(
                args['csv_file_name'],
                parse_dates=[0],
                index_col=0,
                sep='|'
            ).sort_index()
        except FileNotFoundError:
            csv=None

        if csv is not None:
            # CSV exists.

            # Determine if we still want to save to CSV or send report
            balance_prev=csv.tail(1).BRL.values[0]

            balance_change_for_csv=(
                abs(
                    balance.BRL.sum() -
                    balance_prev
                )>args['csv_threshold']
            )

            balance_change_for_report=(
                abs(
                    balance.BRL.sum() -
                    balance_prev
                )>args['report_threshold']
            )

            # CSV writting parameters
            to_csv_mode='a'
            to_csv_header=False
        else:
            # Set to send report because this is the first run
            balance_change_for_csv=True
            balance_change_for_report=True

            # CSV doesn't exist.
            # CSV writting parameters
            to_csv_mode='w'
            to_csv_header=True

        # Append to an existent CSV only if balance changed
        if balance_change_for_csv:
            (
                balance
                .reset_index()
                .assign(time=lambda table: table.time.apply(lambda timecell: timecell.isoformat()))
            ).to_csv(
                args['csv_file_name'],
                sep='|',
                index=False,
                header=to_csv_header,
                mode=to_csv_mode,
            )

        # Now reload a complete and up to date CSV
        balance_history=pandas.read_csv(
            args['csv_file_name'],
            parse_dates=[0],
            index_col=0,
            sep='|'
        ).sort_index()

    else: # no CSV
        balance_history=balance

    # At this point we have the following:
    # - balances: DataFrame with BRL balance per token
    # - balance_history: Time series of summarized balances
    # - balance_prev: Previous balance (only if historical CSV available)

    # Function to merge several dicts
    dmerge = lambda *args: dict(itertools.chain(*[d.items() for d in args]))

    report_tokens=dict(
        balance_history  = balance_history,
        balances         = balances,
        balance          = balance_history.tail(1).BRL.values[0],
        balance_prev     = balance_prev
    )

    report_tokens=dmerge(
        report_tokens,
        dict(
            balance_var      = report_tokens['balance']-report_tokens['balance_prev'],
            balance_pct_change = (report_tokens['balance']/report_tokens['balance_prev'])-1,
            balance_growth     = (report_tokens['balance']/balance_history.head(1).BRL.values[0])-1,
            balance_growth_period = '{}m{}d'.format(
                int((balance_history.index[-1]-balance_history.index[0]).days/30),
                int((balance_history.index[-1]-balance_history.index[0]).days%30)
            )
        )
    )

    if balance_change_for_report and args['TELEGRAM_CHAT_ID'] and args['TELEGRAM_BOT_ID']:
        send_telegram_report(
            args['TELEGRAM_CHAT_ID'],
            args['TELEGRAM_BOT_ID'],
            dmerge(
                report_tokens,
                dict(
                    balances = (
                        balances.style
                        .format('{:,.2f} BRL')
                        .to_string()
                    )
                )
            )
        )


    if balance_change_for_report and args['mail_recipient']:
        send_mail_report(
            args['mail_recipient'],
            dmerge(
                report_tokens,
                dict(
                    balances = (
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
        )


if __name__ == "__main__":
    main()