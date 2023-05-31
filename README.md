# Calcula e salva seu saldo do Mercado Bitcoin

Este programa:

- Busca saldo em BRL de todos os seus tokens no Mercado Bitcoin
- Calcula saldo consolidado
- Atualiza um CSV caso o saldo tenha mudado
- Manda o saldo atual por e-mail junto com algumas estatísticas

## Como usá-lo

```shell
balancemb.py \
    --id 06…05 \
    --secret 10…19 \
    --treshold 5 \
    --csv balances.txt \
    --csv-fund-name 'Nome arbitrário do fundo' \
    --mail seu_email@mail.net
```

Sendo:

- `id` e `secret`: suas credenciais obtidas em https://www.MercadoBitcoin.com.br/plataforma/chaves-api
- `treshold`: variação menor do que este valor será desconsiderado
- `csv`: nome do arquivo CSV para registrar o saldo
- `csv-fund-name`: um nome qualquer para etiquetar o saldo no CSV
- `mail`: endereço para enviar pequeno relatório por e-mail

O CSV acumula os valores como uma série histórica. Registra a hora UTC, o nome do fundo (passado em `csv-fund-name`) e o saldo consolidado em BRL. Assim:

```csv
time|fund|BRL
2023-05-31T19:30:47.407006+00:00|Nome arbitrário do fundo|36595.57
2023-05-31T20:50:14.708121+00:00|Nome arbitrário do fundo|36576.22
```

O e-mail enviado tem esta cara:

> Current balance: **36,576.22 BRL**.
>
> Previous balance: **34,595.72 BRL**.
>
> Variation: **1,980.50 BRL**.
>
> Percent change: **5.72%**.
>
> Brakedown by tokens and coins:
> | 	| Total (BRL) |
> ------|--------------
> | **abfy** | 336.42 BRL |
> | **brl**	 | 36,229.86 BRL |
> | **psgft** | 9.40 BRL |
> | **wemix** | 0.54 BRL |

Eu rodo isso a cada meia hora via crontab, assim:

```crontab
0,30 * * * * cd $HOME/Notebooks/MercadoBitcoinBalance && ./balancemb.py --id 0…5 --secret 1…9 --treshold 5 --csv balances.txt --csv-fund-name 'Nome arbitrário do fundo' --mail seu_email@mail.net
```

É necessário Python 3, Pandas e nada mais para rodar este programa.

Para conseguir enviar e-mails, seu sistema (Linux, obviamente) de forma geral precisa estar configurado como cliente de mail. [Eis um exemplo para configurar o postfix do Fedora](https://fedoramagazine.org/use-postfix-to-get-email-from-your-fedora-system/).

Depois, eu uso o CSV junto com o [investor](https://github.com/avibrazil/investor) para acompanhar performance.