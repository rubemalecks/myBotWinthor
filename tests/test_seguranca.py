import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from modulos import database
from modulos.seguranca import LimiteTaxa


class SegurancaTests(unittest.TestCase):
    def test_taxa_expira_e_memoria_e_limitada(self):
        taxa = LimiteTaxa(max_chaves=2)
        with patch('modulos.seguranca.time.monotonic', return_value=0):
            self.assertTrue(taxa.permitir('a', 1))
            self.assertFalse(taxa.permitir('a', 1))
        with patch('modulos.seguranca.time.monotonic', return_value=61):
            self.assertTrue(taxa.permitir('a', 1))
            taxa.permitir('b', 1)
            taxa.permitir('c', 1)
            self.assertEqual(len(taxa.registros), 2)

    def test_execucao_rejeita_escrita_lock_e_multiplas_instrucoes(self):
        for sql in ('DELETE FROM PCEST', 'SELECT * FROM PCEST FOR UPDATE',
                    'SELECT 1 FROM DUAL; DROP TABLE PCEST', 'BEGIN NULL; END;',
                    'WITH X AS (SELECT 1 FROM DUAL) DELETE FROM PCEST', 'SELECT /* comentario */ 1 FROM DUAL'):
            with self.subTest(sql=sql), self.assertRaises(ValueError), patch.object(database, 'conectar') as conectar:
                database.executar_consulta(sql, {})
            conectar.assert_not_called()
        database.validar_select("SELECT 'UPDATE' AS TEXTO FROM DUAL")

    def test_concorrencia_limitada_e_sessao_read_only(self):
        with patch.object(database, '_abrir_conexao') as abrir, patch.object(database, 'Timer'):
            conexao = abrir.return_value.__enter__.return_value
            with ExitStack() as pilha:
                for _ in range(4):
                    pilha.enter_context(database.conectar())
                with self.assertRaises(RuntimeError):
                    with database.conectar():
                        pass
                self.assertEqual(abrir.call_count, 4)
                self.assertEqual(conexao.call_timeout, 8000)
                conexao.cursor.return_value.__enter__.return_value.execute.assert_called_with('SET TRANSACTION READ ONLY')
            with database.conectar():
                pass

    def test_timeout_cancela_e_libera_slot(self):
        with patch.object(database, '_abrir_conexao') as abrir, patch.object(database, 'Timer') as timer:
            timer.return_value.start.side_effect = lambda: timer.call_args.args[1]()
            with self.assertRaises(RuntimeError):
                with database.conectar():
                    pass
            abrir.return_value.__enter__.return_value.cancel.assert_called_once()
        with patch.object(database, '_abrir_conexao'), patch.object(database, 'Timer'):
            with database.conectar():
                pass

    def test_resultado_grande_nao_e_truncado_silenciosamente(self):
        with patch.object(database, 'conectar') as conectar:
            cursor = conectar.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.description = [('COLUNA',)]
            cursor.fetchmany.return_value = [(1,)] * 5001
            with self.assertRaises(RuntimeError):
                database.executar_consulta('SELECT COLUNA FROM PCEST', {})
            cursor.fetchmany.assert_called_once_with(5001)
            cursor.fetchall.assert_not_called()

    def test_formula_protege_parametro_preco_programado(self):
        from modulos.formulas import explicar_formula
        resultado = {'personalizada': True, 'nome': 'Regra', 'expressao': 'preco / custo',
                     'preco': 20, 'custo': 10, 'percentual': 100}
        args = {'resultado': resultado, 'parametros': {'PCTABPR.PTABELA': 98765}}
        self.assertNotIn('98765', explicar_formula(20, 10, True, **args))
        self.assertIn('98765', explicar_formula(20, 10, True, exibir_preco_programado=True, **args))
        self.assertNotIn('98765', explicar_formula(20, 10, False, exibir_preco_programado=True, **args))

    def test_consulta_custos_valida_catalogo_apenas_uma_vez(self):
        import tempfile
        from pathlib import Path
        from modulos import permissoes
        from modulos.campos_mensagem import preparar_mensagens
        with tempfile.TemporaryDirectory() as pasta, patch.object(permissoes, 'ARQUIVO_DADOS', Path(pasta) / 'dados.json'), patch.object(database, 'listar_colunas_custos', return_value=[{'variavel': 'pcest_custoreal'}, {'variavel': 'pcest_custofin'}]) as catalogo:
            preparar_mensagens({'custos': '{pcest_custoreal} {pcest_custofin} {pcest_custoreal}'})
            catalogo.assert_called_once()

    def test_nome_trata_curingas_como_texto(self):
        with patch.object(database, 'executar_consulta', return_value=[]) as executar:
            database.pesquisar_produtos('ABC%_')
        sql, params = executar.call_args.args
        self.assertIn('ESCAPE', sql)
        self.assertEqual(params['NOME'], r'%ABC\%\_%')

    def test_bot_interrompe_antes_dos_handlers_ao_exceder_limite(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from telegram.ext import ApplicationHandlerStop
        from modulos import bot
        update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=None,
                                 effective_message=SimpleNamespace(reply_text=AsyncMock()))
        with patch.object(bot._limite_telegram, 'permitir', side_effect=[False, True]), self.assertRaises(ApplicationHandlerStop):
            asyncio.run(bot.registrar_recebimento_telegram(update, None))
        update.effective_message.reply_text.assert_awaited_once()

    def test_imagem_grande_rejeitada_antes_do_decoder(self):
        from modulos import leitor_barras
        with patch.object(leitor_barras.cv2, 'imdecode') as decodificar, self.assertRaises(ValueError):
            leitor_barras.ler_codigo_barras(b'x' * (5 * 1024 * 1024 + 1))
        decodificar.assert_not_called()

    def test_telegram_rejeita_codigo_com_sql_antes_de_consultar(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from modulos import bot
        update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=AsyncMock()))
        with patch.object(bot, 'consultar_produto') as consultar:
            asyncio.run(bot.processar_codigo(update, "1 OR 1=1; DELETE FROM PCEST"))
        consultar.assert_not_called()
        update.effective_message.reply_text.assert_awaited_once()

    def test_payload_na_busca_por_nome_permanece_em_bind(self):
        ataque = "ABC' OR 1=1 --"
        with patch.object(database, 'executar_consulta', return_value=[]) as consultar:
            database.pesquisar_produtos(ataque)
        sql, binds = consultar.call_args.args
        self.assertNotIn(ataque, sql)
        self.assertIn(ataque, binds['NOME'])

    def test_oracle_client_nao_carrega_dll_de_servidor_remoto(self):
        for caminho in ('//invasor.invalid/client', r'\\invasor.invalid\client', 'https://invasor.invalid/client'):
            with self.subTest(caminho=caminho), self.assertRaises(ValueError):
                database.validar_diretorio_cliente(caminho)

    def test_codigo_do_painel_nao_interpreta_html_de_usuarios(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[1] / 'modulos'
        for nome in ('painel_admin.py', 'painel_formulas.py'):
            texto = (raiz / nome).read_text(encoding='utf-8')
            for perigoso in ('.innerHTML', '.outerHTML', 'insertAdjacentHTML(', 'document.write(', 'eval('):
                self.assertNotIn(perigoso, texto)

    def test_corpo_chunked_sem_tamanho_e_recusado_ao_exceder_limite(self):
        import asyncio
        from unittest.mock import AsyncMock
        from modulos.seguranca import ProtecaoHTTP
        app = AsyncMock()
        middleware = ProtecaoHTTP(app, lambda r: None, lambda r: None, lambda: None)
        scope = {'type': 'http', 'method': 'POST', 'path': '/api/formulas/draft',
                 'headers': [(b'host', b'127.0.0.1')], 'client': ('127.0.0.1', 123),
                 'query_string': b'', 'session': {'csrf': 'teste'}}
        receber = AsyncMock(side_effect=[{'type': 'http.request', 'body': b'x' * 40000, 'more_body': True},
                                       {'type': 'http.request', 'body': b'x' * 40000, 'more_body': False}])
        enviar = AsyncMock()
        asyncio.run(middleware(scope, receber, enviar))
        app.assert_not_awaited()
        self.assertEqual(enviar.call_args_list[0].args[0]['status'], 413)
        self.assertTrue(middleware.operacoes.acquire(blocking=False))
        middleware.operacoes.release()

    def test_callback_produto_com_indice_unicode_nao_chega_a_consulta(self):
        import asyncio
        import time
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from modulos import bot
        query = SimpleNamespace(data='pcsel:token:²', answer=AsyncMock())
        update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(type='private'))
        context = SimpleNamespace(user_data={'selecao_produto': {'token': 'token', 'criado': time.monotonic(), 'opcoes': [('1', 'Filial 1')]}})
        with patch.object(bot, 'processar_codigo', new_callable=AsyncMock) as consulta:
            asyncio.run(bot.clique_contexto_produto(update, context))
        consulta.assert_not_awaited()
        query.answer.assert_awaited_once_with('Opção inválida.', show_alert=True)
