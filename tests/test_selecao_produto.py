import asyncio
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from modulos import bot


class SelecaoProdutoTests(unittest.TestCase):
    def test_pergunta_filial_e_regiao_antes_de_enviar_preco(self):
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
            effective_message=SimpleNamespace(reply_text=AsyncMock()),
            effective_chat=SimpleNamespace(type='private'))
        context = SimpleNamespace(user_data={})
        produto = {'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                   'ptabela': 12, 'numregiao': 2, 'nome_tabela': 'VAREJO'}
        with ExitStack() as stack:
            for nome, valor in [('tem_permissao', True), ('obter_escopo_acesso', {}),
                               ('obter_opcoes_consulta', {'perguntar_filial': True, 'perguntar_regiao': True}),
                               ('listar_filiais_produto', [{'codfilial': '1'}, {'codfilial': '2'}]),
                               ('pode_ver_custo', False), ('pode_ver_margem_produto', False),
                               ('pode_ver_margem_departamento', False)]:
                stack.enter_context(patch.object(bot, nome, return_value=valor))
            stack.enter_context(patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True))
            consulta = stack.enter_context(patch.object(bot, 'consultar_com_log', new_callable=AsyncMock,
                return_value=[produto, {**produto, 'numregiao': 3, 'nome_tabela': 'ATACADO'}]))
            enviar = stack.enter_context(patch.object(bot, 'enviar_mensagem', new_callable=AsyncMock))
            asyncio.run(bot.processar_codigo(update, '6', context))
            self.assertEqual(context.user_data['selecao_produto']['tipo'], 'filial')
            enviar.assert_not_awaited()
            for tipo in ('filial', 'regiao'):
                fluxo = context.user_data['selecao_produto']
                self.assertEqual(fluxo['tipo'], tipo)
                update.callback_query = SimpleNamespace(data=f"pcsel:{fluxo['token']}:0",
                    answer=AsyncMock(), edit_message_reply_markup=AsyncMock())
                asyncio.run(bot.clique_contexto_produto(update, context))
            enviar.assert_awaited_once()
            escopo = consulta.call_args.args[-1]
            self.assertEqual(escopo['filiais_permitidas'], ['1'])
            self.assertEqual(escopo['tabelas_permitidas'], ['2'])
            self.assertNotIn('selecao_produto', context.user_data)

    def test_opcao_unica_e_automatica_e_restringe_custos_e_margens(self):
        for origem in ('manual', 'foto', 'nome'):
            with self.subTest(origem=origem), ExitStack() as stack:
                update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
                    effective_message=SimpleNamespace(reply_text=AsyncMock()))
                context = SimpleNamespace(user_data={})
                produto = {'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                           'ptabela': 12, 'numregiao': 2, 'nome_tabela': 'VAREJO'}
                escopos = []

                async def consultar(update, tipo, funcao, *args, **kwargs):
                    escopos.append((tipo, dict(args[-1])))
                    return [produto] if tipo == 'produto' else []

                for nome, valor in [('tem_permissao', True), ('obter_escopo_acesso', {}),
                                   ('obter_opcoes_consulta', {'perguntar_filial': True, 'perguntar_regiao': True}),
                                   ('listar_filiais_produto', [{'codfilial': '1'}]),
                                   ('pode_ver_custo', True), ('pode_ver_margem_produto', True),
                                   ('pode_ver_margem_departamento', True)]:
                    stack.enter_context(patch.object(bot, nome, return_value=valor))
                stack.enter_context(patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True))
                stack.enter_context(patch.object(bot, 'consultar_com_log', side_effect=consultar))
                enviar = stack.enter_context(patch.object(bot, 'enviar_mensagem', new_callable=AsyncMock))
                asyncio.run(bot.processar_codigo(update, '6', context, origem))
                update.effective_message.reply_text.assert_not_awaited()
                enviar.assert_awaited_once()
                self.assertIn('VAREJO', enviar.call_args.args[1])
                self.assertIn('Filial: 1', enviar.call_args.args[1])
                self.assertNotIn('selecao_produto', context.user_data)
                self.assertEqual([tipo for tipo, _ in escopos], ['produto', 'custos_e_margem_produto'])
                for tipo, escopo in escopos[1:]:
                    self.assertEqual(escopo, {'filiais_permitidas': ['1'], 'tabelas_permitidas': ['2']}, tipo)

    def test_pergunta_somente_categoria_com_varias_opcoes(self):
        for varias_filiais in (False, True):
            with self.subTest(varias_filiais=varias_filiais), ExitStack() as stack:
                update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
                    effective_message=SimpleNamespace(reply_text=AsyncMock()))
                context = SimpleNamespace(user_data={})
                produto = {'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                           'ptabela': 12, 'numregiao': 2, 'nome_tabela': 'VAREJO'}
                produtos = [produto] if varias_filiais else [produto, {**produto, 'numregiao': 3}]
                filiais = [{'codfilial': '1'}, {'codfilial': '2'}] if varias_filiais else [{'codfilial': '1'}]
                for nome, valor in [('tem_permissao', True), ('obter_escopo_acesso', {}),
                                   ('obter_opcoes_consulta', {'perguntar_filial': True, 'perguntar_regiao': True}),
                                   ('listar_filiais_produto', filiais),
                                   ('pode_ver_custo', False), ('pode_ver_margem_produto', False),
                                   ('pode_ver_margem_departamento', False)]:
                    stack.enter_context(patch.object(bot, nome, return_value=valor))
                stack.enter_context(patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True))
                stack.enter_context(patch.object(bot, 'consultar_com_log', new_callable=AsyncMock, return_value=produtos))
                enviar = stack.enter_context(patch.object(bot, 'enviar_mensagem', new_callable=AsyncMock))
                asyncio.run(bot.processar_codigo(update, '6', context))
                fluxo = context.user_data['selecao_produto']
                self.assertEqual(fluxo['tipo'], 'filial' if varias_filiais else 'regiao')
                self.assertEqual(len(fluxo['opcoes']), 2)
                if not varias_filiais:
                    self.assertEqual(fluxo['selecoes'], {'filial': '1'})
                enviar.assert_not_awaited()

    def test_selecao_antiga_nao_contorna_permissao_revogada(self):
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
                                 effective_message=SimpleNamespace(reply_text=AsyncMock()))
        with patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True), \
             patch.object(bot, 'obter_escopo_acesso', return_value={'filiais_permitidas': ['2']}), \
             patch.object(bot, 'consultar_com_log', new_callable=AsyncMock) as consulta:
            asyncio.run(bot.processar_codigo(update, '6', selecoes={'filial': '1'}))
            consulta.assert_not_awaited()
            self.assertIn('não está mais autorizada', update.effective_message.reply_text.call_args.args[0])
