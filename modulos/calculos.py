"""Cálculos compartilhados de ganho sobre o custo de entrada."""
from decimal import Decimal


def ganho_sobre_custo(preco_venda, custo_entrada):
    if preco_venda is None or custo_entrada is None:
        return None
    preco = Decimal(str(preco_venda))
    custo = Decimal(str(custo_entrada))
    if preco <= 0 or custo <= 0:
        return None
    return (preco - custo) / custo * 100
