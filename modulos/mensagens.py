"""Modelos de texto do bot, com variáveis limitadas por bloco de permissão."""
import logging
from string import Formatter

from modulos.permissoes import (
    obter_mensagens_personalizadas, salvar_mensagens_personalizadas,
)

logger = logging.getLogger(__name__)
LIMITE_MODELO = 2500


def _modelo(grupo, titulo, padrao, **exemplo):
    return {'grupo': grupo, 'titulo': titulo, 'padrao': padrao, 'exemplo': exemplo}


MODELOS = {
    'produto': _modelo('Produto', 'Identificação do produto',
        '📦 CONSULTA DE PRODUTO\n\n🏷️ {descricao}\n🔢 Código: {codprod}\n\n',
        descricao='PRODUTO DE EXEMPLO', codprod='1663'),
    'preco': _modelo('Produto', 'Preço por tabela',
        '📋 {tabela}\n\n💰 PREÇO DE VENDA\n➡️ {preco}\n',
        tabela='1 - VAREJO', regiao='1', preco='R$ 18,29'),
    'programado': _modelo('Produto', 'Preço programado (exige permissão)',
        '\n▫️ Programado: {programado}\n', programado='R$ 18,29'),
    'filial': _modelo('Produto', 'Filial selecionada',
        '\n🏢 Filial: {filial}\n', filial='1'),
    'custos_titulo': _modelo('Custos e entrada', 'Título dos custos',
        '\n━━━━━━━━━━━━━━━━━━━━\n🔐 INFORMAÇÕES RESTRITAS\n'),
    'custos': _modelo('Custos e entrada', 'Custo da última entrada',
        '📥 Custo última entrada: {custo}\n📅 Última entrada: {data_entrada}\n',
        custo='R$ 13,59000', data_entrada='30/07/2026', filial='1'),
    'nota': _modelo('Custos e entrada', 'Nota e fornecedor',
        '🚚 DADOS DA ENTRADA\n\n📄 NF: {nota}\n🏭 Fornecedor: {codfornec} - {fornecedor}\n'
        '📆 Emissão NF: {emissao}\n🔢 Transação: {transacao}\n',
        nota='123456', codfornec='278', fornecedor='FORNECEDOR DE EXEMPLO',
        emissao='28/07/2026', transacao='31696'),
    'lucro_titulo': _modelo('Lucro do produto', 'Título do lucro do produto',
        '\n━━━━━━━━━━━━━━━━━━━━\n📈 MARGEM DO PRODUTO\n'),
    'lucro_produto': _modelo('Lucro do produto', 'Percentual por produto e tabela',
        '\n📋 {tabela}\n📈 Lucro presumido sobre o custo: {lucro}\n',
        tabela='VAREJO', lucro='34,58%', filial='1'),
    'departamento': _modelo('Departamento', 'Identificação do departamento',
        '📊 MARGEM DO MIX — DEPARTAMENTO\n🏷️ {codigo} - {departamento}\n🏢 Filial: {filial}\n\n',
        codigo='108', departamento='DEPARTAMENTO DE EXEMPLO', filial='1'),
    'departamento_tabela': _modelo('Departamento', 'Resultado por tabela',
        '━━━━━━━━━━━━━━━━━━━━\n📋 {regiao} - {tabela}\n\n💰 Soma dos preços: {precos}\n'
        '📊 Lucro presumido sobre o custo: {lucro}\n',
        regiao='1', tabela='VAREJO', precos='R$ 100,00', lucro='42,86%'),
    'departamento_custos': _modelo('Departamento', 'Detalhes (exige custos)',
        '📥 Soma dos custos: {custos}\n📈 Diferença bruta: {diferenca}\n'
        '📦 Produtos analisados: {validos} de {total}\n⚠️ Sem preço válido: {sem_preco}\n'
        '⚠️ Sem custo: {sem_custo}\nℹ️ Custo zero: {custo_zero}\n',
        custos='R$ 70,00', diferenca='R$ 30,00', validos='2', total='3',
        sem_preco='1', sem_custo='0', custo_zero='0'),
    'departamento_rodape': _modelo('Departamento', 'Rodapé da análise',
        'ℹ️ Simulação de 1 unidade por produto com preço e custo válidos. '
        'Não representa faturamento nem lucro realizado. '
        'Estimativa bruta sobre o custo de entrada, antes de impostos e outras despesas.'),
    'formula_produto': _modelo('Fórmula', 'Identificação do produto',
        '📐 FÓRMULA DO PRODUTO\n🏷️ {descricao}\n🔢 CODPROD: {codprod}\n',
        descricao='PRODUTO DE EXEMPLO', codprod='1663'),
    'formula_departamento': _modelo('Fórmula', 'Identificação do departamento',
        '📐 FÓRMULA DO DEPARTAMENTO\n🏷️ {codigo} — {departamento}\n',
        codigo='108', departamento='DEPARTAMENTO DE EXEMPLO'),
    'formula_base': _modelo('Fórmula', 'Expressão do cálculo',
        '📐 Fórmula: {formula}\n',
        formula='(Preço de venda − Custo de entrada) ÷ Custo de entrada × 100'),
    'formula_valores': _modelo('Fórmula', 'Valores (exige custos)',
        'Venda: R$ {venda}\nCusto: R$ {custo}\n', venda='18,29000', custo='13,59000'),
    'formula_calculo': _modelo('Fórmula', 'Substituição numérica (exige custos)',
        'Cálculo: ({venda} − {custo}) ÷ {custo} × 100\n', venda='18,29000', custo='13,59000'),
    'formula_resultado': _modelo('Fórmula', 'Percentual calculado',
        '📈 Lucro presumido sobre o custo: {lucro}\n', lucro='34,58%'),
    'pesquisa_nome': _modelo('Pesquisa e seleção', 'Resultado da busca por nome',
        '🔎 Pesquisa: {termo}\n\n📦 Exibindo {quantidade} produto(s).\n\n'
        '👇 Toque no produto desejado para consultar o preço.', termo='PRODUTO', quantidade='3'),
    'perguntar_filial': _modelo('Pesquisa e seleção', 'Pergunta de filial', '🏢 Qual filial deseja consultar?'),
    'perguntar_regiao': _modelo('Pesquisa e seleção', 'Pergunta de região/tabela', '📋 Qual região/tabela de preço deseja consultar?'),
    'nao_encontrado': _modelo('Avisos de consulta', 'Produto não encontrado',
        '❌ Produto não encontrado nas filiais permitidas ao seu perfil.'),
    'sem_preco': _modelo('Avisos de consulta', 'Produto sem preço autorizado',
        '⚠️ Produto não está precificado em nenhuma tabela de preço permitida ao seu perfil.'),
    'erro_consulta': _modelo('Avisos de consulta', 'Falha na consulta', '⚠️ Não foi possível consultar o WinThor.'),
    'custos_vazios': _modelo('Avisos de consulta', 'Nenhum custo localizado',
        '\n🔐 INFORMAÇÕES RESTRITAS\n\nNenhum registro de custo encontrado.'),
    'lucro_indisponivel': _modelo('Avisos de consulta', 'Lucro sem custo disponível',
        '\n📈 MARGEM DO PRODUTO\n\nNão há custo disponível para calcular a margem do produto.'),
    'departamento_vazio': _modelo('Avisos de consulta', 'Departamento sem produtos precificados',
        '⚠️ Nenhum produto com preço nesta filial e região.'),
}


def validar_modelo(chave, texto):
    if chave not in MODELOS:
        raise ValueError('Tipo de mensagem desconhecido.')
    if not isinstance(texto, str) or not texto.strip() or len(texto) > LIMITE_MODELO:
        raise ValueError(f'O texto deve ter de 1 a {LIMITE_MODELO} caracteres.')
    try:
        for _, campo, formato, conversao in Formatter().parse(texto):
            if campo is not None and (campo not in MODELOS[chave]['exemplo'] or formato or conversao):
                raise ValueError(f'Variável não permitida: {{{campo}}}. Use as variáveis indicadas neste modelo.')
    except ValueError as erro:
        raise ValueError(f'Modelo inválido: {erro}') from erro
    return texto


def listar_modelos():
    salvos = obter_mensagens_personalizadas()
    return [{'id': chave, **modelo, 'texto': salvos.get(chave, modelo['padrao']),
             'personalizado': chave in salvos} for chave, modelo in MODELOS.items()]


def salvar_modelos(alteracoes):
    if not isinstance(alteracoes, dict) or not alteracoes or not set(alteracoes).issubset(MODELOS):
        raise ValueError('Informe os tipos de mensagem que deseja alterar.')
    for chave, texto in alteracoes.items():
        if texto is not None:
            validar_modelo(chave, texto)
    salvar_mensagens_personalizadas(alteracoes)
    return listar_modelos()


def previa_modelo(chave, texto):
    return validar_modelo(chave, texto).format_map(MODELOS[chave]['exemplo'])


def renderizar_mensagem(chave, **valores):
    modelo = MODELOS[chave]
    try:
        texto = obter_mensagens_personalizadas().get(chave, modelo['padrao'])
        validar_modelo(chave, texto)
    except (RuntimeError, ValueError):
        logger.warning('Modelo de mensagem inválido ou indisponível: %s. Usando padrão.', chave)
        texto = modelo['padrao']
    # Somente as variáveis deste bloco entram no contexto. Nunca avalia expressões.
    contexto = {campo: str(valores.get(campo, 'Não informado')) for campo in modelo['exemplo']}
    return texto.format_map(contexto)
