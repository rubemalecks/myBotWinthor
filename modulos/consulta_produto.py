"""Consulta manual usando as mesmas proteções de acesso ao Oracle do aplicativo."""
from modulos.database import executar_consulta


def consultar_identificacao(codigo):
    codigo = str(codigo)
    if not codigo.isascii() or not codigo.isdecimal() or not 0 < int(codigo) < 10**15:
        raise ValueError('Informe um CODPROD positivo.')
    return executar_consulta("""SELECT CODPROD, DESCRICAO, CODAUXILIAR
        FROM PCPRODUT WHERE CODPROD = :codigo AND DTEXCLUSAO IS NULL""", {'codigo': int(codigo)})


if __name__ == '__main__':
    for produto in consultar_identificacao(input('CODPROD: ').strip()):
        print('Código:', produto['codprod'])
        print('Descrição:', produto['descricao'])
        print('Código de barras:', produto['codauxiliar'])
