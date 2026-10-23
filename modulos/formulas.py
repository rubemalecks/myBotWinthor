"""Explicação do cálculo, com proteção dos valores de custo."""
from decimal import Decimal

from modulos.calculos import ganho_sobre_custo
from modulos.mensagens import renderizar_mensagem


def explicar_formula(preco, custo, exibir_valores=False, agregado=False, resultado=None, parametros=None, departamento=None):
    if resultado and resultado.get('personalizada'):
        texto = f'🧮 Regra: {resultado["nome"]}\n'
        texto += renderizar_mensagem('formula_base', formula=resultado['expressao'])
        if exibir_valores:
            texto += (f'Preço original: R$ {Decimal(str(preco or 0)):.5f}\n'
                      f'Custo original: R$ {Decimal(str(custo or 0)):.5f}\n'
                      f'Preço calculado: R$ {Decimal(str(resultado["preco"] or 0)):.5f}\n'
                      f'Custo calculado: R$ {Decimal(str(resultado["custo"] or 0)):.5f}\n')
            for campo, valor in (parametros or {}).items():
                texto += f'{campo}: {valor if valor is not None else "Não informado"}\n'
        percentual = resultado['percentual']
        return texto + (renderizar_mensagem('formula_resultado', lucro=f'{Decimal(str(percentual)):.2f}'.replace('.', ',') + '%')
                        if percentual is not None else '📈 Percentual indisponível: os valores calculados precisam ser positivos.\n')
    if departamento and departamento.get('formulas_ativas'):
        texto = '📐 Fórmula do departamento: soma(base × percentual de cada produto / 100) ÷ soma(base) × 100\n'
        texto += 'Base: custo calculado depois dos ajustes de cada produto.\n'
        for regra in departamento['regras_aplicadas']:
            texto += f'🧮 {regra["nome"]}: {regra["expressao"]}\n'
        if exibir_valores:
            texto += f'Base total: {departamento["base_formulas"]}\nGanho calculado: {departamento["ganho_formulas"]}\n'
        percentual = departamento['percentual_formula']
        return texto + (renderizar_mensagem('formula_resultado', lucro=f'{Decimal(str(percentual)):.2f}'.replace('.', ',') + '%')
                        if percentual is not None else '📈 Percentual indisponível: não há base de cálculo válida.\n')
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
