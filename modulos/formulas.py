"""Explicação do cálculo, com proteção dos valores de custo."""
from decimal import Decimal

from modulos.calculos import ganho_sobre_custo
from modulos.mensagens import renderizar_mensagem


def explicar_formula(preco, custo, exibir_valores=False, agregado=False):
    base = ('(Soma dos preços − Soma dos custos) ÷ Soma dos custos × 100'
            if agregado else '(Preço de venda − Custo de entrada) ÷ Custo de entrada × 100')
    texto = renderizar_mensagem('formula_base', formula=base)
    ganho = ganho_sobre_custo(preco, custo)
    if exibir_valores:
        def numero(valor):
            return f'{Decimal(str(valor)):.5f}'.replace('.', ',') if valor is not None else 'Não informado'
        texto += renderizar_mensagem('formula_valores', venda=numero(preco), custo=numero(custo))
        if ganho is not None:
            texto += renderizar_mensagem('formula_calculo', venda=numero(preco), custo=numero(custo))
    texto += (renderizar_mensagem('formula_resultado', lucro=f'{ganho:.2f}'.replace('.', ',') + '%')
              if ganho is not None else '📈 Percentual indisponível: preço/custo ausente, zero ou negativo.\n')
    return texto
