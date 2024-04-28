# Calcula, salva e reporta seu saldo do Mercado Bitcoin

Este programa:

- Busca saldo em BRL de todos os seus tokens no Mercado Bitcoin
- Calcula saldo consolidado
- Atualiza um CSV caso o saldo tenha mudado
- Manda o saldo atual por e-mail ou Telegram junto com algumas estatísticas

É necessário Python 3, Pandas e nada mais para rodar este programa.

Para conseguir enviar e-mails, seu sistema (Linux, obviamente) de forma geral precisa estar configurado como cliente de mail. [Eis um exemplo para configurar o postfix do Fedora](https://fedoramagazine.org/use-postfix-to-get-email-from-your-fedora-system/).

Depois, eu uso o CSV junto com o [investorzilla](https://github.com/avibrazil/investorzilla) para acompanhar performance.

# Como usar a API

```python
import MercadoBitcoinBalance

# Suas credenciais obtidas em https://www.MercadoBitcoin.com.br/plataforma/chaves-api
MP_API_ID='06…05'
MP_API_SECRET='10…19'

mb=MercadoBitcoinBalance.MercadoBitcoinAPI(MP_API_ID,MP_API_SECRET)

balances=mb.get_BRL_balances()
```

# Como usar na linha de comando

Instale:

```shell
pip install MercadoBitcoinBalance --user
```

Use:

```shell
balancemb \
    --mb-id 06…05 \
    --mb-secret 10…19 \
    --csv-threshold 1 \
    --csv balances.txt \
    --csv-fund-name 'Nome arbitrário do fundo' \
    --report-threshold 20 \
    --mail seu_email@mail.net \
    --telegram-chat-id 12345678 \
    --telegram-bot-id '13…Wk'
```

Sendo:

- `mb-id` e `mb-secret`: suas credenciais obtidas em https://www.MercadoBitcoin.com.br/plataforma/chaves-api
- `csv-threshold`: só atualiza CSV se variação do saldo é maior do que este valor
- `csv`: nome do arquivo CSV para registrar o saldo
- `csv-fund-name`: um nome qualquer para etiquetar o saldo no CSV
- `report-threshold`: só manda relatório se variação do saldo, desde último relatório, é maior do que este valor
- `mail`: endereço para enviar pequeno relatório por e-mail; não manda se omitido
- `telegram-chat-id`: o ID do seu usuário Telegram; não manda se omitido
- `telegram-bot-id`: o ID do bot que você deve criar em https://t.me/BotFather

O CSV acumula os valores como uma série temoral. Registra a hora UTC (UTC, sempre UTC, sempre), o nome do fundo (passado em `csv-fund-name`) e o saldo consolidado em BRL. Assim:

```csv
time|fund|BRL|reported
2023-05-31T19:30:47.407006+00:00|Nome arbitrário do fundo|36595.57|1
2023-05-31T20:50:14.708121+00:00|Nome arbitrário do fundo|36576.22|0
```

O e-mail e mensagem de Telegram enviados tem esta cara:

> Current balance: **36,576.22 BRL**.
>
> Previous balance: **34,595.72 BRL**.
>
> Variation: **1,980.50 BRL**.
>
> Percent change: **5\.72%**.
>
> Historycal growth: **4%** in **0m2d**.
>
> Brakedown by tokens and coins:
>
> |  | Total (BRL) |
> |--|-------------|
> | **brl** | 36,229.86 BRL |
> | **abfy** | 336\.42 BRL |
> | **psgft** | 9\.40 BRL |
> | **wemix** | 0\.54 BRL |

Eu rodo isso a cada meia hora via crontab, assim:

```crontab
*/30 * * * * ~/.local/bin/balancemb --mb-id 06…05 --mb-secret 10…19 --csv-threshold 2 --csv ~/investorzilla-my/mercadobitcoin-balances.txt --csv-fund-name 'Nome arbitrário do fundo' --report-threshold 20 --telegram-chat-id 12345678 --telegram-bot-id '11223344::A…k'
```

Adicionalmente, rodo todos os dias às 20:15 e forço envio de relatório (`--report-threshold -1`) por Telegram:
```crontab
15 20 * * * ~/.local/bin/balancemb --mb-id 06…05 --mb-secret 10…19 --csv-threshold 5 --csv ~/investorzilla-my/mercadobitcoin-balances.txt --csv-fund-name 'Nome arbitrário do fundo' --report-threshold -1 --telegram-chat-id 12345678 --telegram-bot-id '11223344::A…k'
```

Ou seja, atualizo saldo consolidado em `balances.txt` a cada meia hora, não mando relatório mas mando saldos por Telegram caso houver variação de mais de 20 BRL.
Além do mais, todo dia às 20:15 manda o saldo atual, mesmo que não houve variação.