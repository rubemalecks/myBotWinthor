import os
import asyncio
import logging
import json
import re
import sqlite3
import threading
import time
from io import BytesIO
from decimal import Decimal

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from database import consultar_produto, consultar_custos, pesquisar_produtos
from leitor_barras import ler_codigo_barras
from margem_departamento import (
    listar_departamentos, obter_departamento, listar_filiais_departamento,
    listar_regioes_ativas, calcular_margens_departamento, formatar_relatorio,
    consultar_margens_departamento_produto,
)
from permissoes import (
    inicializar, eh_admin_bot as eh_admin, perfil_teste_ativo, pode_ver_custo, pode_ver_margem_produto, pode_ver_margem_departamento, tem_permissao,
    obter_configuracao,
    registrar_usuario as registrar_usuario_perfil,
    autorizar, revogar, listar_usuarios, definir_apelido, identificar_usuario,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# O log HTTP do cliente Telegram inclui a URL com o token do bot.
logging.getLogger('httpx').setLevel(logging.WARNING)


def registrar_consulta_log(update, tipo, etapa, **detalhes):
    usuario = update.effective_user
    dados = {
        'requisicao': update.update_id,
        'usuario_id': usuario.id,
        'nome': str(usuario.full_name)[:128],
        'username': str(usuario.username or '')[:64],
        'consulta': tipo,
        'etapa': etapa,
        **detalhes,
    }
    logger.info('CONSULTA %s', json.dumps(dados, ensure_ascii=False, default=str))


async def consultar_com_log(update, tipo, funcao, *argumentos, **detalhes):
    inicio = time.monotonic()
    registrar_consulta_log(update, tipo, 'INICIO', **detalhes)
    try:
        resultado = await asyncio.to_thread(funcao, *argumentos)
    except Exception as erro:
        registrar_consulta_log(update, tipo, 'ERRO', **detalhes,
                               erro=type(erro).__name__,
                               codigos=re.findall(r'(?:ORA|DPI|DPY)-\d+', str(erro)),
                               duracao_ms=round((time.monotonic() - inicio) * 1000))
        raise
    registrar_consulta_log(update, tipo, 'CONCLUIDO', **detalhes,
                           registros=len(resultado) if isinstance(resultado, list) else int(resultado is not None),
                           duracao_ms=round((time.monotonic() - inicio) * 1000))
    return resultado


async def registrar_usuario(update: Update):
    usuario = update.effective_user
    return await asyncio.to_thread(
        registrar_usuario_perfil,
        usuario.id,
        usuario.full_name,
        usuario.username,
    )


async def verificar_acesso_consulta(update: Update):
    perfil = await registrar_usuario(update)
    teste = await asyncio.to_thread(perfil_teste_ativo, update.effective_user.id)
    if teste is not None:
        perfil = teste
    if eh_admin(update.effective_user.id) or perfil and perfil['aprovado']:
        return True
    registrar_consulta_log(update, 'acesso', 'NEGADO', motivo='Perfil aguardando aprovação ou bloqueado')
    await update.effective_message.reply_text(
        '⏳ Seu acesso está aguardando aprovação no painel administrativo.\n'
        f'🔑 Seu ID do Telegram: {update.effective_user.id}'
    )
    return False


def formatar_moeda(valor, casas=2):
    if valor is None:
        return 'Não informado'
    texto = f'{Decimal(str(valor)):,.{casas}f}'
    return 'R$ ' + texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def formatar_data(valor):
    if valor is None:
        return 'Não informada'
    return valor.strftime('%d/%m/%Y') if hasattr(valor, 'strftime') else str(valor)


def calcular_margem(preco_venda, custo_entrada):
    if preco_venda is None or custo_entrada is None:
        return None
    preco, custo = Decimal(str(preco_venda)), Decimal(str(custo_entrada))
    if preco <= 0:
        return None
    return f'{((preco - custo) / preco) * 100:.2f}'.replace('.', ',') + '%'


def validar_id(argumentos):
    if len(argumentos) != 1:
        return None
    valor = argumentos[0]
    return int(valor) if valor.isascii() and valor.isdecimal() and int(valor) > 0 else None


async def enviar_mensagem(update, texto):
    destino = update.effective_message
    parte = ''
    for linha in texto.splitlines(keepends=True):
        if parte and len(parte) + len(linha) > 4000:
            await destino.reply_text(parte)
            parte = ''
        while len(linha) > 4000:
            await destino.reply_text(linha[:4000])
            linha = linha[4000:]
        parte += linha
    if parte:
        await destino.reply_text(parte)


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso_consulta(update):
        return
    await update.effective_message.reply_text(
        '🤖 BUSCA PREÇO - WINTHOR\n\n'
        '🔢 Pesquise por CODPROD, CODAUXILIAR ou CODAUXILIAR2, conforme suas permissões.\n'
        '🔎 Digite parte do nome do produto (mínimo 3 caracteres), se habilitado.\n'
        '📸 Envie uma foto do código de barras, se habilitado.\n\n'
        'Comandos: /start /ajuda /comandos /meuid'
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await registrar_usuario(update)
    mensagem = (
        '📖 AJUDA - BUSCA PREÇO\n\n'
        '🔢 Números: consulta por código.\n'
        '🔎 Texto: pesquisa por nome e exibe até 10 opções.\n'
        '📸 Foto: leitura do código de barras.\n\n'
        '/start - Iniciar\n/ajuda - Ajuda\n/meuid - Meu ID\n'
    )
    if eh_admin(update.effective_user.id):
        mensagem += '\n🔐 Aprove usuários e configure cada perfil no painel administrativo da rede.\n'
    if await asyncio.to_thread(pode_ver_margem_departamento, update.effective_user.id):
        mensagem += '\n/margem [departamento] - Margem por departamento\n'
    await update.effective_message.reply_text(mensagem)


async def comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista os comandos conforme a permissão do usuário."""
    await registrar_usuario(update)
    user_id = update.effective_user.id
    mensagem = (
        '🤖 BUSCA PREÇO - COMANDOS\n\n'
        '📦 CONSULTAS\n'
        '/start - Iniciar o bot\n'
        '/ajuda - Ver ajuda\n'
        '/comandos - Ver comandos disponíveis\n'
        '/meuid - Consultar seu ID\n\n'
        '🔎 PESQUISAR PRODUTOS\n'
        '• Digite um código interno ou de barras\n'
        '• Digite parte do nome do produto\n'
        '• Envie uma foto do código de barras\n'
    )
    if await asyncio.to_thread(pode_ver_margem_departamento, user_id):
        mensagem += (
            '\n📊 MARGEM POR DEPARTAMENTO\n'
            '/margem - Selecionar departamento para análise\n'
            '/margem 113 - Analisar departamento 113\n'
            '/cancelarmargem - Cancelar análise de margem\n'
        )
    if await asyncio.to_thread(pode_ver_custo, user_id):
        mensagem += '\n🔐 Seu perfil permite consultar custos detalhados dos produtos.\n'
    if eh_admin(user_id):
        mensagem += '\n👑 ADMINISTRAÇÃO\n• Aprove usuários e configure permissões individuais no painel web\n'
    await enviar_mensagem(update, mensagem)


async def meu_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await registrar_usuario(update)
    usuario = update.effective_user
    await update.effective_message.reply_text(f'👤 Nome: {usuario.full_name}\n🔑 ID: {usuario.id}')


async def comando_autorizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not eh_admin(update.effective_user.id):
        await update.effective_message.reply_text('⛔ Você não tem permissão.')
        return
    if not context.args or len(context.args) > 2:
        await update.effective_message.reply_text(
            '⚠️ Uso: /autorizar 123456789 joao\n'
            'O apelido é opcional: /autorizar 123456789'
        )
        return
    user_id = validar_id(context.args[:1])
    if user_id is None:
        await update.effective_message.reply_text('⚠️ Informe um ID numérico válido.')
        return
    apelido = context.args[1] if len(context.args) == 2 else None
    try:
        await asyncio.to_thread(autorizar, user_id, apelido)
        texto = f'✅ Usuário autorizado!\n🔑 ID: {user_id}'
        if apelido:
            texto += f'\n👤 Apelido: {apelido.lower()}'
        texto += '\n🔓 Acesso a custos e margens liberado.'
        await update.effective_message.reply_text(texto)
    except sqlite3.IntegrityError:
        await update.effective_message.reply_text('⚠️ Esse apelido já pertence a outro usuário.')
    except ValueError as erro:
        await update.effective_message.reply_text(f'⚠️ {erro}')
    except Exception:
        logger.exception('Erro ao autorizar usuário')
        await update.effective_message.reply_text('⚠️ Erro ao autorizar usuário.')


async def comando_revogar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not eh_admin(update.effective_user.id):
        await update.effective_message.reply_text('⛔ Você não tem permissão.')
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text('⚠️ Uso: /revogar joao ou /revogar 123456789')
        return
    identificador = context.args[0]
    if identificador.isascii() and identificador.isdecimal() and eh_admin(int(identificador)):
        await update.effective_message.reply_text('⚠️ Não é possível revogar o administrador principal.')
        return
    try:
        removido = await asyncio.to_thread(revogar, identificador)
        if removido is None:
            await update.effective_message.reply_text('❌ Usuário ou apelido não encontrado.')
            return
        await update.effective_message.reply_text(
            f'✅ Autorização revogada!\n👤 Referência: {identificador}\n🔑 ID: {removido}'
        )
    except ValueError as erro:
        await update.effective_message.reply_text(f'⚠️ {erro}')
    except Exception:
        logger.exception('Erro ao revogar usuário')
        await update.effective_message.reply_text('⚠️ Erro ao revogar autorização.')


async def comando_apelido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not eh_admin(update.effective_user.id):
        await update.effective_message.reply_text('⛔ Você não tem permissão.')
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text('⚠️ Uso: /apelido 123456789 joao')
        return
    identificador, apelido = context.args
    try:
        user_id = await asyncio.to_thread(definir_apelido, identificador, apelido)
        await update.effective_message.reply_text(
            f'✅ Apelido atualizado!\n🔑 ID: {user_id}\n👤 Apelido: {apelido.lower()}'
        )
    except sqlite3.IntegrityError:
        await update.effective_message.reply_text('⚠️ Esse apelido já pertence a outro usuário.')
    except ValueError as erro:
        await update.effective_message.reply_text(f'⚠️ {erro}')
    except Exception:
        logger.exception('Erro ao definir apelido')
        await update.effective_message.reply_text('⚠️ Erro ao definir apelido.')


async def comando_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not eh_admin(update.effective_user.id):
        await update.effective_message.reply_text('⛔ Você não tem permissão.')
        return
    try:
        usuarios = await asyncio.to_thread(listar_usuarios)
        mensagem = f'🔐 USUÁRIOS AUTORIZADOS\n\n👑 Administrador: {os.getenv("TELEGRAM_ADMIN_ID")}\n\n'
        if not usuarios:
            mensagem += 'Nenhum usuário adicional autorizado.'
        else:
            for user_id, data, apelido in usuarios:
                mensagem += (f'👤 Apelido: {apelido or "Sem apelido"}\n'
                             f'🔑 ID: {user_id}\n'
                             f'📅 Autorizado em: {data}\n\n')
        await enviar_mensagem(update, mensagem)
    except Exception:
        logger.exception('Erro ao listar usuários')
        await update.effective_message.reply_text('⚠️ Erro ao listar usuários.')


def montar_mensagem_precos(produtos):
    primeiro = produtos[0]
    mensagem = (f'📦 CONSULTA DE PRODUTO\n\n🏷️ {primeiro["descricao"]}\n'
                f'🔢 Código: {primeiro["codprod"]}\n\n')
    for i, item in enumerate(produtos):
        if i:
            mensagem += '\n━━━━━━━━━━━━━━━━━━━━\n\n'
        nome_tabela = item['nome_tabela']
        if len(produtos) > 1:
            nome_tabela = f'{item["numregiao"]} - {nome_tabela}'
        mensagem += (f'📋 {nome_tabela}\n\n💰 PREÇO DE VENDA\n'
                     f'➡️ {formatar_moeda(item["pvenda"])}\n\n'
                     f'▫️ Programado: {formatar_moeda(item["ptabela"])}\n')
    return mensagem


def montar_mensagem_custos(custos, produtos):
    if not custos:
        return '\n🔐 INFORMAÇÕES RESTRITAS\n\nNenhum registro de custo encontrado.'
    mensagem = '\n━━━━━━━━━━━━━━━━━━━━\n🔐 INFORMAÇÕES RESTRITAS\n'
    varias_filiais = len(custos) > 1
    for item in custos:
        mensagem += '\n'
        if varias_filiais:
            mensagem += f'🏢 FILIAL {item["codfilial"]}\n\n'
        mensagem += (f'📥 Custo última entrada: {formatar_moeda(item["custoultent"], 5)}\n'
                     f'📅 Última entrada: {formatar_data(item["dtultent"])}\n')
        if item['numtransent'] is not None:
            mensagem += ('🚚 DADOS DA ENTRADA\n\n'
                         f'📄 NF: {item["numnota"]}\n'
                         f'🏭 Fornecedor: {item["codfornec"]} - {item["nome_fornecedor"] or "Não informado"}\n'
                         f'📆 Emissão NF: {formatar_data(item["dtemissao"])}\n'
                         f'🔢 Transação: {item["numtransent"]}\n')
        else:
            mensagem += '📄 NF correspondente à data da última entrada não localizada.\n'
        if varias_filiais:
            mensagem += '\n━━━━━━━━━━━━━━━━━━━━\n'
    return mensagem


def montar_mensagem_margens(custos, produtos):
    if not custos:
        return '\n📈 MARGEM DO PRODUTO\n\nNão há custo disponível para calcular a margem do produto.'
    mensagem = '\n━━━━━━━━━━━━━━━━━━━━\n📈 MARGEM DO PRODUTO\n'
    varias_filiais = len(custos) > 1
    for item in custos:
        if varias_filiais:
            mensagem += f'\n🏢 FILIAL {item["codfilial"]}\n'
        for produto in produtos:
            margem = calcular_margem(produto['pvenda'], item['custoultent'])
            mensagem += (
                f'\n📋 {produto["nome_tabela"]}\n'
                f'📈 Margem: {margem or "Indisponível"}\n'
            )
    return mensagem


def montar_mensagem_margem_departamento(linhas):
    mensagem = '\n━━━━━━━━━━━━━━━━━━━━\n📊 MARGEM MÉDIA DO DEPARTAMENTO\n'
    if not linhas:
        return mensagem + '\nSem dados válidos para calcular a margem do departamento.\n'
    mensagem += f'🏷️ Departamento: {linhas[0]["codepto"]}\n'
    for item in linhas:
        margem = calcular_margem(item['total_precos'], item['total_custos'])
        mensagem += (f'\n🏢 Filial {item["codfilial"]} · 📋 {item["nome_tabela"]}\n'
                     f'📈 Margem do departamento: {margem or "Indisponível"}\n'
                     f'📦 Produtos considerados: {item["produtos_validos"]}\n')
    return mensagem + '\nℹ️ Margem do mix: uma unidade por produto, antes de impostos e outras despesas.\n'


async def processar_codigo(update: Update, codigo: str, context=None, origem='manual'):
    codigo = codigo.strip()
    if not codigo or not codigo.isascii() or not codigo.isdecimal():
        await update.effective_message.reply_text('⚠️ Envie um código numérico válido.')
        return
    if not await verificar_acesso_consulta(update):
        return
    user_id = update.effective_user.id
    if origem == 'foto':
        if not await asyncio.to_thread(tem_permissao, user_id, 'consulta_preco') or not await asyncio.to_thread(
            tem_permissao, user_id, 'buscar_por_foto'
        ):
            await update.effective_message.reply_text('⛔ Seu perfil não permite consulta por foto.')
            return
        campos_busca = ('codauxiliar', 'codauxiliar2')
    elif origem == 'nome':
        if not await asyncio.to_thread(tem_permissao, user_id, 'consulta_preco'):
            await update.effective_message.reply_text('⛔ Seu perfil não permite esta consulta.')
            return
        campos_busca = ('codprod',)
    else:
        if not await asyncio.to_thread(tem_permissao, user_id, 'consulta_preco'):
            await update.effective_message.reply_text('⛔ Seu perfil não permite consultar preços.')
            return
        campos_busca = []
        for campo, permissao in (
            ('codprod', 'buscar_codprod'),
            ('codauxiliar', 'buscar_codauxiliar'),
            ('codauxiliar2', 'buscar_codauxiliar2'),
        ):
            if await asyncio.to_thread(tem_permissao, user_id, permissao):
                campos_busca.append(campo)
        campos_busca = tuple(campos_busca)
        if not campos_busca:
            await update.effective_message.reply_text(
                '⛔ Seu perfil não permite pesquisa por CODPROD, CODAUXILIAR ou CODAUXILIAR2.'
            )
            return
    try:
        produtos = await consultar_com_log(
            update, 'produto', consultar_produto, codigo, campos_busca,
            origem=origem, codigo=codigo, campos=list(campos_busca),
            tabelas=['PCPRODUT', 'PCTABPR', 'PCREGIAO'])
        if not produtos:
            await update.effective_message.reply_text(
                '❌ PRODUTO NÃO ENCONTRADO\n\n'
                'Verifique o código ou se existe preço em uma região ativa.'
            )
            return
        mensagem = montar_mensagem_precos(produtos)
        ver_custos = await asyncio.to_thread(pode_ver_custo, user_id)
        ver_margem = await asyncio.to_thread(pode_ver_margem_produto, user_id)
        if ver_custos or ver_margem:
            try:
                custos = await consultar_com_log(
                    update, 'custos_e_margem_produto', consultar_custos, produtos[0]['codprod'],
                    codprod=produtos[0]['codprod'], exibir_custos=ver_custos, exibir_margem=ver_margem)
                if ver_custos:
                    mensagem += montar_mensagem_custos(custos, produtos)
                if ver_margem:
                    mensagem += montar_mensagem_margens(custos, produtos)
            except Exception:
                logger.exception('Erro na consulta restrita de custos')
                mensagem += '\n🔐 INFORMAÇÕES DO PERFIL\n\n⚠️ Dados de custo/margem indisponíveis no momento.'
        if await asyncio.to_thread(pode_ver_margem_departamento, user_id):
            try:
                margens_departamento = await consultar_com_log(
                    update, 'margem_departamento_do_produto',
                    consultar_margens_departamento_produto, produtos[0]['codprod'],
                    codprod=produtos[0]['codprod'])
                mensagem += montar_mensagem_margem_departamento(margens_departamento)
            except Exception:
                logger.exception('Erro ao consultar margem do departamento do produto')
                mensagem += '\n📊 MARGEM MÉDIA DO DEPARTAMENTO\n⚠️ Indisponível no momento.\n'
        await enviar_mensagem(update, mensagem)
    except Exception:
        logger.exception('Erro na consulta do WinThor')
        await update.effective_message.reply_text('⚠️ Não foi possível consultar o WinThor.')


async def pesquisar_por_nome(update: Update, nome: str):
    if not await verificar_acesso_consulta(update):
        return
    if not await asyncio.to_thread(tem_permissao, update.effective_user.id, 'consulta_preco'):
        await update.effective_message.reply_text('⛔ Seu perfil não permite consultar preços.')
        return
    nome = nome.strip()
    if len(nome) < 3:
        await update.effective_message.reply_text('⚠️ Digite pelo menos 3 caracteres para pesquisar pelo nome.')
        return
    try:
        resultados = await consultar_com_log(update, 'pesquisa_por_nome', pesquisar_produtos, nome,
                                            termo=nome[:200])
        if not resultados:
            await update.effective_message.reply_text('❌ Nenhum produto encontrado com esse nome.')
            return
        mais_de_dez = len(resultados) > 10
        botoes = []
        for item in resultados[:10]:
            codigo = str(item['codprod'])
            descricao = str(item['descricao'])
            rotulo = f'{codigo} - {descricao}'
            if len(rotulo) > 60:
                rotulo = rotulo[:57] + '...'
            botoes.append([InlineKeyboardButton(rotulo, callback_data=f'produto:{codigo}')])
        mensagem = (f'🔎 Pesquisa: {nome}\n\n'
                    f'📦 Exibindo {len(botoes)} produto(s).\n\n'
                    '👇 Toque no produto desejado para consultar o preço.')
        if mais_de_dez:
            mensagem += ('\n\n⚠️ Foram encontrados mais de 10 produtos. '
                         'Estou mostrando os 10 primeiros. '
                         'Digite um nome mais específico para refinar a busca.')
        await update.effective_message.reply_text(
            mensagem, reply_markup=InlineKeyboardMarkup(botoes)
        )
    except Exception:
        logger.exception('Erro na pesquisa por nome')
        await update.effective_message.reply_text('⚠️ Erro ao pesquisar produtos.')


async def selecionar_produto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Botões funcionam apenas em conversa privada.
    if update.effective_chat.type != 'private':
        return
    codigo = query.data.removeprefix('produto:')
    if not codigo.isascii() or not codigo.isdecimal():
        await update.effective_message.reply_text('⚠️ Seleção inválida.')
        return
    await processar_codigo(update, codigo, context, origem='nome')


async def consultar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso_consulta(update):
        return
    texto = update.effective_message.text.strip()
    fluxo = context.user_data.get('margem_fluxo')
    if fluxo and fluxo.get('fase') == 'departamento_texto':
        if not await margem_autorizada(update):
            context.user_data.pop('margem_fluxo', None)
            await update.effective_message.reply_text('⛔ Acesso não autorizado.')
            return
        await escolher_departamento(update, context, texto)
        return
    if texto.isascii() and texto.isdecimal():
        await processar_codigo(update, texto, context)
    else:
        await pesquisar_por_nome(update, texto)


async def consultar_por_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = update.effective_message
    if not await verificar_acesso_consulta(update):
        return
    if not await asyncio.to_thread(tem_permissao, update.effective_user.id, 'consulta_preco') or not await asyncio.to_thread(
        tem_permissao, update.effective_user.id, 'buscar_por_foto'
    ):
        await mensagem.reply_text('⛔ Seu perfil não permite consulta por foto.')
        return
    await mensagem.reply_text('📸 Foto recebida!\n🔎 Identificando código de barras...')
    registrar_consulta_log(update, 'foto', 'LEITURA_INICIADA')
    try:
        if mensagem.photo:
            arquivo = await mensagem.photo[-1].get_file()
        elif mensagem.document and (mensagem.document.mime_type or '').startswith('image/'):
            arquivo = await mensagem.document.get_file()
        else:
            await mensagem.reply_text('⚠️ Envie uma foto do código de barras.')
            return
        buffer = BytesIO()
        await arquivo.download_to_memory(out=buffer)
        codigo = await asyncio.to_thread(ler_codigo_barras, buffer.getvalue())
        registrar_consulta_log(update, 'foto', 'CODIGO_IDENTIFICADO' if codigo else 'CODIGO_NAO_IDENTIFICADO', codigo=codigo)
        if not codigo:
            await mensagem.reply_text(
                '❌ Não consegui identificar o código de barras.\n\n'
                '📸 Tente novamente com boa iluminação, código inteiro visível e imagem focada.'
            )
            return
        await mensagem.reply_text(f'✅ Código identificado: {codigo}\n🔎 Consultando no WinThor...')
        await processar_codigo(update, codigo, context, origem='foto')
    except Exception:
        logger.exception('Erro ao processar foto do código de barras')
        await mensagem.reply_text('⚠️ Não foi possível processar a foto.')



# ==========================================
# MARGEM DO MIX POR DEPARTAMENTO (RESTRITO)
# ==========================================

async def margem_autorizada(update):
    await registrar_usuario(update)
    return (update.effective_chat.type == 'private'
            and await asyncio.to_thread(pode_ver_margem_departamento, update.effective_user.id))


def botoes_em_linhas(opcoes, prefixo, rotulo):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(rotulo(item), callback_data=f'{prefixo}:{i}')]
        for i, item in enumerate(opcoes)
    ])


async def comando_margem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await margem_autorizada(update):
        await update.effective_message.reply_text('⛔ Comando exclusivo para usuários autorizados.')
        return
    context.user_data.pop('margem_fluxo', None)
    termo = ' '.join(context.args).strip()
    if not termo:
        context.user_data['margem_fluxo'] = {'fase': 'departamento_texto'}
        await update.effective_message.reply_text(
            '📊 MARGEM POR DEPARTAMENTO\n\n'
            'Digite o código ou parte do nome do departamento.\n'
            'Exemplo: 113 ou /margem 113\n\n'
            'Para cancelar, use /cancelarmargem.'
        )
        return
    await escolher_departamento(update, context, termo)


async def escolher_departamento(update, context, termo):
    try:
        if termo.isascii() and termo.isdecimal():
            departamento = await asyncio.to_thread(obter_departamento, int(termo))
            if departamento:
                await selecionar_departamento_margem(update, context, departamento)
                return
        resultados = await asyncio.to_thread(listar_departamentos, termo)
        if not resultados:
            await update.effective_message.reply_text('❌ Nenhum departamento encontrado. Tente outro código ou nome.')
            return
        if len(resultados) == 1:
            await selecionar_departamento_margem(update, context, resultados[0])
            return
        opcoes = resultados[:20]
        context.user_data['margem_fluxo'] = {'fase': 'departamento_botao', 'opcoes': opcoes}
        aviso = ('\n⚠️ Há mais de 20 resultados. Refine o nome.' if len(resultados) > 20 else '')
        await update.effective_message.reply_text(
            f'📦 Selecione o departamento:{aviso}',
            reply_markup=botoes_em_linhas(opcoes, 'mgd',
                lambda d: f'{d["codepto"]} - {d["descricao"]}'[:60]),
        )
    except Exception:
        logger.exception('Erro ao buscar departamentos')
        await update.effective_message.reply_text('⚠️ Erro ao consultar departamentos.')


async def selecionar_departamento_margem(update, context, departamento):
    try:
        filiais = await asyncio.to_thread(listar_filiais_departamento, departamento['codepto'])
        if not filiais:
            await update.effective_message.reply_text('⚠️ Nenhuma filial com produtos desse departamento.')
            context.user_data.pop('margem_fluxo', None)
            return
        fluxo = {'fase': 'filial', 'departamento': departamento,
                 'filiais': [str(f['codfilial']) for f in filiais]}
        context.user_data['margem_fluxo'] = fluxo
        if len(fluxo['filiais']) == 1:
            await selecionar_filial_margem(update, context, fluxo['filiais'][0])
            return
        await update.effective_message.reply_text(
            '🏢 Qual filial deseja analisar?',
            reply_markup=botoes_em_linhas(fluxo['filiais'], 'mgf', lambda f: f'Filial {f}'),
        )
    except Exception:
        logger.exception('Erro ao listar filiais')
        await update.effective_message.reply_text('⚠️ Erro ao consultar filiais.')


async def selecionar_filial_margem(update, context, filial):
    fluxo = context.user_data.get('margem_fluxo')
    if not fluxo or filial not in fluxo.get('filiais', []):
        await update.effective_message.reply_text('⚠️ Seleção expirada. Use /margem novamente.')
        return
    fluxo['filial'] = filial
    fluxo['fase'] = 'modo_regiao'
    await update.effective_message.reply_text(
        f'🏢 Filial {filial} selecionada.\n\n'
        '📋 Como deseja analisar as tabelas de preço?',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('📊 Todas as tabelas ativas, separadamente', callback_data='mgmodo:todas')],
            [InlineKeyboardButton('📋 Escolher tabela específica', callback_data='mgmodo:escolher')],
        ]),
    )


async def executar_margem(update, context, regiao=None):
    fluxo = context.user_data.get('margem_fluxo')
    if not fluxo or 'filial' not in fluxo:
        await update.effective_message.reply_text('⚠️ Consulta expirada. Use /margem novamente.')
        return
    # Invalida os botões anteriores; uma nova consulta exige reiniciar o fluxo.
    context.user_data.pop('margem_fluxo', None)
    await update.effective_message.reply_text('⏳ Calculando a margem do departamento...')
    try:
        linhas = await consultar_com_log(
            update, 'margem_departamento', calcular_margens_departamento,
            fluxo['departamento']['codepto'], fluxo['filial'], regiao,
            departamento=fluxo['departamento']['codepto'], filial=fluxo['filial'], regiao=regiao or 'todas',
        )
        incluir_custos = await asyncio.to_thread(pode_ver_custo, update.effective_user.id)
        relatorio = formatar_relatorio(
            fluxo['departamento'], fluxo['filial'], linhas,
            incluir_custos=incluir_custos,
        )
        await enviar_mensagem(update, relatorio)
    except Exception:
        logger.exception('Erro ao calcular margem do departamento')
        await update.effective_message.reply_text('⚠️ Erro ao calcular a margem do departamento.')


async def clique_margem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await margem_autorizada(update):
        await query.answer('Acesso não autorizado.', show_alert=True)
        return
    fluxo = context.user_data.get('margem_fluxo')
    if not fluxo:
        await query.answer('Seleção expirada. Use /margem novamente.', show_alert=True)
        return
    dado = query.data
    tipo, valor = dado.split(':', 1)
    fase_esperada = {'mgd': 'departamento_botao', 'mgf': 'filial',
                     'mgmodo': 'modo_regiao', 'mgr': 'regiao'}
    if fluxo.get('fase') != fase_esperada.get(tipo):
        await query.answer('Esta seleção não está mais ativa.', show_alert=True)
        return
    await query.answer()
    if tipo == 'mgd':
        opcoes = fluxo.get('opcoes', [])
        indice = int(valor)
        if indice >= len(opcoes):
            return
        await selecionar_departamento_margem(update, context, opcoes[indice])
    elif tipo == 'mgf':
        filiais = fluxo['filiais']
        indice = int(valor)
        if indice >= len(filiais):
            return
        await selecionar_filial_margem(update, context, filiais[indice])
    elif tipo == 'mgmodo':
        if valor == 'todas':
            await executar_margem(update, context)
        elif valor == 'escolher':
            try:
                regioes = await asyncio.to_thread(
                    listar_regioes_ativas, fluxo['departamento']['codepto'])
                if not regioes:
                    await update.effective_message.reply_text('⚠️ Não há tabelas ativas para esse departamento.')
                    return
                fluxo['regioes'] = regioes
                fluxo['fase'] = 'regiao'
                await update.effective_message.reply_text(
                    '📋 Escolha a tabela de preço:',
                    reply_markup=botoes_em_linhas(regioes, 'mgr',
                        lambda r: f'{r["numregiao"]} - {r["nome_tabela"]}'[:60]),
                )
            except Exception:
                logger.exception('Erro ao listar regiões')
                await update.effective_message.reply_text('⚠️ Erro ao consultar tabelas.')
    elif tipo == 'mgr':
        regioes = fluxo.get('regioes', [])
        indice = int(valor)
        if indice >= len(regioes):
            return
        await executar_margem(update, context, regioes[indice]['numregiao'])


async def cancelar_margem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('margem_fluxo', None)
    await update.effective_message.reply_text('✅ Consulta de margem cancelada.')



# ==========================================
def main():
    inicializar()
    from painel_admin import iniciar_painel, obter_url_acesso
    servidor, thread_painel = iniciar_painel()
    logger.info(
        'Painel administrativo ativo em %s',
        obter_url_acesso(),
    )
    configuracao = obter_configuracao()
    token = configuracao['TELEGRAM_BOT_TOKEN'].strip()
    thread_bot = None

    if token:
        def executar_bot():
            try:
                app = ApplicationBuilder().token(token).build()
                privado = filters.ChatType.PRIVATE
                app.add_handler(CommandHandler('start', iniciar, filters=privado))
                app.add_handler(CommandHandler('ajuda', ajuda, filters=privado))
                app.add_handler(CommandHandler('comandos', comandos, filters=privado))
                app.add_handler(CommandHandler('meuid', meu_id, filters=privado))
                app.add_handler(CommandHandler('margem', comando_margem, filters=privado))
                app.add_handler(CommandHandler('cancelarmargem', cancelar_margem, filters=privado))
                app.add_handler(CallbackQueryHandler(
                    clique_margem, pattern=r'^(mgd|mgf|mgmodo|mgr):'
                ))
                app.add_handler(CallbackQueryHandler(
                    selecionar_produto, pattern=r'^produto:[0-9]+$'
                ))
                app.add_handler(MessageHandler(
                    privado & (filters.PHOTO | filters.Document.IMAGE),
                    consultar_por_foto,
                ))
                app.add_handler(MessageHandler(
                    privado & filters.TEXT & ~filters.COMMAND, consultar
                ))
                logger.info(
                    'Bot WinThor iniciado: CODPROD, CODAUXILIAR, CODAUXILIAR2 e foto.'
                )
                app.run_polling(stop_signals=None)
            except Exception:
                logger.exception(
                    'O bot do Telegram não iniciou. O painel continua ativo; '
                    'corrija as configurações e reinicie o serviço.'
                )

        thread_bot = threading.Thread(
            target=executar_bot, name='bot-telegram', daemon=True
        )
        thread_bot.start()
    else:
        logger.warning(
            'Token do Telegram ainda não configurado. Configure-o no painel e '
            'reinicie o serviço para iniciar o bot.'
        )

    try:
        print(
            'Painel administrativo: '
            'acesse o endereco informado no log para configurar o bot.'
        )
        while True:
            time.sleep(1)
    finally:
        servidor.should_exit = True
        thread_painel.join(timeout=10)


if __name__ == '__main__':
    main()
