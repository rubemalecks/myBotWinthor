import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from telegram.error import InvalidToken

os.environ["WEB_ADMIN_USER"] = "admin"
os.environ["WEB_ADMIN_PASSWORD"] = "admin"
os.environ["WEB_SESSION_SECRET"] = "t" * 48
os.environ["TELEGRAM_ADMIN_ID"] = "999"

from fastapi.testclient import TestClient

from modulos import permissoes

_DADOS_INICIAIS_TESTES = tempfile.TemporaryDirectory()
permissoes.ARQUIVO_DADOS = Path(_DADOS_INICIAIS_TESTES.name) / "bootstrap.json"
permissoes.ARQUIVO_LEGADO = Path(_DADOS_INICIAIS_TESTES.name) / "missing.db"
unittest.addModuleCleanup(_DADOS_INICIAIS_TESTES.cleanup)

from modulos import painel_admin
from modulos.painel_admin import app


class PainelAdminTests(unittest.TestCase):
    def test_diagnostico_oracle_informa_codigo_sem_vazar_credenciais(self):
        import oracledb
        cfg={k:'ficticio' for k in ('ORACLE_HOST','ORACLE_SERVICE','ORACLE_USER','ORACLE_PASSWORD')}
        with patch('modulos.painel_admin.testar_conexao_oracle',side_effect=oracledb.NotSupportedError('DPY-3016 senha-ultrassecreta')):
            with self.assertLogs(painel_admin.logger,level='WARNING') as logs:
                resultado=asyncio.run(painel_admin._verificar_oracle(cfg))
        self.assertEqual(resultado['status'],'error')
        self.assertIn('DPY-3016',resultado['message'])
        self.assertIn('criptografia',resultado['message'])
        self.assertNotIn('senha-ultrassecreta',str(resultado)+str(logs.output))

    def test_tentativas_login_concorrentes_nao_apagam_bloqueio(self):
        import threading
        import time
        import httpx
        barreira = threading.Barrier(6)
        def falhar(*args):
            barreira.wait(timeout=5)
            return False
        async def disparar():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1') as cliente:
                return await asyncio.gather(*[cliente.post('/api/login', json={'username': 'admin', 'password': 'incorreta'}) for _ in range(6)])
        with patch('modulos.painel_admin.verificar_senha_admin', side_effect=falhar):
            respostas = asyncio.run(disparar())
        self.assertEqual(sorted(r.status_code for r in respostas), [401] * 5 + [429])
        self.assertGreater(painel_admin._tentativas_login['127.0.0.1'][1], time.monotonic())

    def test_host_rebinding_invalido_e_caminho_dll_remoto_bloqueados(self):
        self.assertEqual(self.client.get('/health', headers={'Host': 'invasor.invalid'}).status_code, 400)
        self.assertEqual(self.client.post('/api/formulas/draft', headers={'X-CSRF-Token': self.csrf, 'Origin': 'http://['}, json={}).status_code, 403)
        with patch('modulos.painel_admin.salvar_configuracoes') as salvar:
            resposta = self.client.put('/api/settings', headers={'X-CSRF-Token': self.csrf},
                json={'settings': {'ORACLE_CLIENT_DIR': '//invasor.invalid/dll'}})
        self.assertEqual(resposta.status_code, 400)
        salvar.assert_not_called()

    def test_api_rejeita_injecao_em_formula_e_variaveis_sem_acessar_oracle(self):
        headers = {'X-CSRF-Token': self.csrf}
        with patch('modulos.painel_formulas.listar_catalogo_formulas') as oracle:
            for filtro in ("PCEST.CUSTOREAL > 1; DELETE FROM PCEST", "__import__('os').system('whoami')", "P.CODPROD IN (SELECT CODPROD FROM PCPRODUT)"):
                resposta = self.client.put('/api/formulas', headers=headers,
                    json={'nome': 'Ataque', 'where': filtro})
                self.assertEqual(resposta.status_code, 400, resposta.text)
            oracle.assert_not_called()
        with patch('modulos.database.listar_colunas_custos') as oracle:
            for texto in ('{pcest_custoreal.__class__}', '{pcest_custoreal!r}', '{__import__}', '{custo:1000000000}'):
                resposta = self.client.post('/api/message-templates/preview', headers=headers,
                    json={'id': 'custos', 'texto': texto})
                self.assertEqual(resposta.status_code, 400, resposta.text)
            oracle.assert_not_called()

    def test_todas_rotas_api_exigem_sessao_e_mutacoes_exigem_csrf(self):
        anonimo = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50001))
        for rota in app.routes:
            if not rota.path.startswith('/api/') or rota.path == '/api/login':
                continue
            path = __import__('re').sub(r'\{[^}]+\}', '123', rota.path)
            for metodo in rota.methods - {'HEAD', 'OPTIONS'}:
                with self.subTest(path=path, metodo=metodo):
                    resposta = anonimo.request(metodo, path, json={})
                    self.assertEqual(resposta.status_code, 401, resposta.text)
                    if metodo not in ('GET', 'HEAD', 'OPTIONS'):
                        resposta = self.client.request(metodo, path, json={})
                        self.assertEqual(resposta.status_code, 403, resposta.text)

    def test_openapi_cabecalhos_payload_e_origem(self):
        self.assertEqual(self.client.get('/openapi.json').status_code, 404)
        resposta = self.client.get('/api/settings')
        self.assertEqual(resposta.headers['cache-control'], 'no-store')
        self.assertEqual(resposta.headers['x-frame-options'], 'DENY')
        headers = {'X-CSRF-Token': self.csrf}
        resposta = self.client.post('/api/formulas/draft', headers=headers, content='x' * 65537)
        self.assertEqual(resposta.status_code, 413)
        resposta = self.client.post('/api/formulas/draft', headers={**headers, 'Origin': 'https://invasor.invalid'}, json={})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.client.get('/api/directories', params={'path': '//servidor/pasta'}).status_code, 400)

    def test_login_remoto_com_senha_padrao_bloqueado(self):
        remoto = TestClient(app, base_url='http://127.0.0.1', client=('192.0.2.10', 50000))
        resposta = remoto.post('/api/login', json={'username': 'admin', 'password': 'admin'})
        self.assertEqual(resposta.status_code, 403, resposta.text)
        resposta = remoto.post('/api/login', headers={'X-Forwarded-For': '127.0.0.1'}, json={'username': 'admin', 'password': 'admin'})
        self.assertEqual(resposta.status_code, 403)

    def test_limite_previas_nega_sem_consultar_oracle(self):
        with patch('modulos.painel_formulas.listar_catalogo_formulas', return_value=[]) as consultar:
            resultados = [self.client.get('/api/formulas/catalog').status_code for _ in range(61)]
        self.assertEqual(resultados[-1], 429)
        self.assertLessEqual(consultar.call_count, 60)

    def test_formula_persiste_custo_base_e_rejeita_tabela_diferente(self):
        from modulos.regras_margem import obter_regras
        headers = {'X-CSRF-Token': self.csrf}
        regra = {'nome': 'Base real', 'todos_produtos': True, 'campo_custo': 'PCEST.CUSTOREAL', 'ajustes': []}
        with patch('modulos.painel_formulas.listar_catalogo_formulas', return_value=[{'campo': 'PCEST.CUSTOREAL', 'numerico': True}]):
            resposta = self.client.put('/api/formulas', headers=headers, json=regra)
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(obter_regras()[0]['campo_custo'], 'PCEST.CUSTOREAL')
            previa = self.client.post('/api/formulas/draft', headers=headers, json=regra)
            self.assertIn('PCEST.CUSTOREAL', previa.json()['expressao'])
            with patch('modulos.painel_formulas.consultar_calculos_formulas_produto', return_value=[]) as consulta:
                previa = self.client.post('/api/formulas/preview', headers=headers, json={'codprod': '6', 'regra': regra})
                self.assertEqual(previa.status_code, 200, previa.text)
                self.assertEqual(consulta.call_args.kwargs['rascunho']['campo_custo'], 'PCEST.CUSTOREAL')
            regra['campo_custo'] = 'PCTABPR.PVENDA'
            resposta = self.client.put('/api/formulas', headers=headers, json=regra)
            self.assertEqual(resposta.status_code, 400)
            self.assertEqual(obter_regras()[0]['campo_custo'], 'PCEST.CUSTOREAL')
            regra['id'] = obter_regras()[0]['id']
            regra.pop('campo_custo')
            resposta = self.client.put('/api/formulas', headers=headers, json=regra)
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertNotIn('campo_custo', obter_regras()[0])

    def test_campos_custo_catalogo_previa_e_salvamento(self):
        headers = {'X-CSRF-Token': self.csrf}
        catalogo = [{'coluna': 'CUSTOFIN', 'variavel': 'pcest_custofin'}]
        with patch('modulos.database.listar_colunas_custos', return_value=catalogo), \
             patch('modulos.database.consultar_custos', return_value=[
                 {'codfilial': 2, 'custoultent': 3, 'dtultent': None, 'pcest_custofin': 4},
                 {'codfilial': 5, 'custoultent': 6, 'dtultent': None, 'pcest_custofin': None}]) as consulta:
            self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get('/api/message-templates/cost-columns').status_code, 401)
            self.assertEqual(self.client.get('/api/message-templates/cost-columns').json()['campos'], catalogo)
            resposta = self.client.post('/api/message-templates/preview', headers=headers,
                json={'id': 'custos', 'texto': '{filial}: {PCEST_CUSTOFIN}', 'codprod': '6'})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertIn('2: R$ 4,00000', resposta.json()['texto'])
            self.assertIn('5: Não informado', resposta.json()['texto'])
            self.assertEqual(permissoes.obter_mensagens_personalizadas(), {})
            self.assertEqual(consulta.call_args.kwargs['texto'], '{filial}: {pcest_custofin}')
            resposta = self.client.put('/api/message-templates', headers=headers,
                json={'templates': {'custos': '{PCEST_CUSTOFIN}'}})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(permissoes.obter_mensagens_personalizadas()['custos'], '{pcest_custofin}')

    def test_coluna_digitada_testa_sem_cadastrar_e_salva_automaticamente(self):
        headers = {'X-CSRF-Token': self.csrf}
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[{'coluna':'EMBALAGEM'}]), patch.object(painel_admin, 'consultar_produto_previa') as consulta:
            consulta.return_value = {'codprod':6,'descricao':'Abobrinha','campos_personalizados':{
                'embalagem':{'valor':'KG','permissao':'consulta_preco'}}}
            resposta = self.client.post('/api/message-templates/preview', headers=headers,
                json={'id':'produto','texto':'{DESCRICAO} {EMBALAGEM}','codprod':'6'})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(resposta.json()['texto'], 'Abobrinha KG')
            self.assertFalse(permissoes.ARQUIVO_DADOS.with_name('campos_produto.json').exists())
            self.assertEqual(consulta.call_args.args[1], [{'coluna':'EMBALAGEM','permissao':'consulta_preco'}])
            resposta = self.client.put('/api/message-templates', headers=headers,
                json={'templates':{'produto':'{DESCRICAO} {EMBALAGEM}'}})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(permissoes.obter_mensagens_personalizadas()['produto'], '{descricao} {embalagem}')
        from modulos.mensagens import renderizar_mensagem
        self.assertEqual(renderizar_mensagem('produto', descricao='Abobrinha', embalagem='KG'), 'Abobrinha KG')

    def test_coluna_inexistente_ou_expressao_nao_persiste(self):
        headers = {'X-CSRF-Token': self.csrf}
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[{'coluna':'EMBALAGEM'}]):
            for texto in ('{NAO_EXISTE}', '{PCPRODUT.EMBALAGEM}', '{embalagem!r}', '{embalagem:10}'):
                resposta = self.client.put('/api/message-templates', headers=headers, json={'templates':{'produto':texto}})
                self.assertEqual(resposta.status_code, 400, resposta.text)
        self.assertEqual(permissoes.obter_mensagens_personalizadas(), {})
        self.assertFalse(permissoes.ARQUIVO_DADOS.with_name('campos_produto.json').exists())

    def test_previa_mensagem_com_campo_real_e_nulo(self):
        headers = {'X-CSRF-Token':self.csrf}
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[{'coluna':'VOLUME'}]), patch.object(painel_admin, 'consultar_produto_previa') as consulta:
            consulta.return_value = {'codprod':6,'descricao':'PRODUTO REAL','campos_personalizados':{
                'volume':{'valor':12,'permissao':'ver_custos'}}}
            resposta = self.client.post('/api/message-templates/preview', headers=headers,
                json={'id':'produto','texto':'{codprod} {descricao} Volume: {volume}','codprod':'6'})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(resposta.json()['texto'], '6 PRODUTO REAL Volume: 12')
            consulta.return_value['campos_personalizados']['volume']['valor'] = None
            resposta = self.client.post('/api/message-templates/preview', headers=headers,
                json={'id':'produto','texto':'Volume: {volume}','codprod':'6'})
            self.assertEqual(resposta.json()['texto'], 'Volume: Não informado')
            consulta.return_value = None
            self.assertEqual(self.client.post('/api/message-templates/preview', headers=headers,
                json={'id':'produto','texto':'{volume}','codprod':'6'}).status_code, 404)
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[]), patch.object(painel_admin, 'consultar_produto_previa') as consulta:
            self.assertEqual(self.client.post('/api/message-templates/preview', headers=headers,
                json={'id':'produto','texto':'{senha}','codprod':'6'}).status_code, 400)
            consulta.assert_not_called()

    def test_confirmar_formula_sem_produto_nao_consulta_oracle_nem_salva(self):
        anonimo = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        self.assertEqual(anonimo.post('/api/formulas/draft', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/formulas/draft', json={}).status_code, 403)
        headers = {'X-CSRF-Token':self.csrf}
        with patch('modulos.painel_formulas.listar_catalogo_formulas') as catalogo, patch('modulos.painel_formulas.consultar_calculos_formulas_produto') as consultar:
            resposta = self.client.post('/api/formulas/draft', headers=headers, json={'ajustes':[
                {'alvo':'custo','operacao':'+','tipo':'valor','valor':'10'}]})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertIn('(custo) + 10', resposta.json()['expressao'])
            self.assertFalse(permissoes.ARQUIVO_DADOS.with_name('formulas_margem.json').exists())
            invalida = self.client.post('/api/formulas/draft', headers=headers, json={'ajustes':[
                {'alvo':'custo','operacao':'+','tipo':'valor','valor':'abc'}]})
            self.assertEqual(invalida.status_code, 400)
            catalogo.assert_not_called()
            consultar.assert_not_called()

    def test_formulas_exigem_sessao_csrf_e_persistem_localmente(self):
        anonimo = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        self.assertEqual(anonimo.get('/api/formulas').status_code, 401)
        regra = {'nome':'Custo com frete','produtos':[6],'ajustes':[{'alvo':'custo','operacao':'+','tipo':'valor','valor':'2'}]}
        self.assertEqual(self.client.put('/api/formulas', json=regra).status_code, 403)
        headers = {'X-CSRF-Token':self.csrf}
        with patch('modulos.painel_formulas.listar_catalogo_formulas', return_value=[]):
            resposta = self.client.put('/api/formulas', json=regra, headers=headers)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        identificador = resposta.json()['regras'][0]['id']
        self.assertTrue(permissoes.ARQUIVO_DADOS.with_name('formulas_margem.json').exists())
        with patch('modulos.painel_formulas.listar_catalogo_formulas', return_value=[]), patch('modulos.painel_formulas.consultar_calculos_formulas_produto', return_value=[]) as consulta:
            resposta = self.client.post('/api/formulas/preview', headers=headers, json={'codprod':'6','regra':regra})
            self.assertEqual(resposta.status_code, 200)
            consulta.assert_called_once()
        self.assertEqual(self.client.delete('/api/formulas/'+identificador, headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/formulas').json()['regras'], [])

    def test_campos_produto_exigem_login_e_csrf(self):
        anonimo = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        self.assertEqual(anonimo.get('/api/product-fields').status_code, 401)
        self.assertEqual(anonimo.get('/api/product-fields/catalog').status_code, 401)
        self.assertEqual(anonimo.put('/api/product-fields', json={'campos': []}).status_code, 401)
        self.assertEqual(self.client.put('/api/product-fields', json={'campos': []}).status_code, 403)

    def test_campo_habilitado_disponibiliza_variavel_na_mensagem(self):
        headers = {'X-CSRF-Token': self.csrf}
        catalogo = [{'coluna': 'CODAUXILIAR', 'variavel': 'codauxiliar', 'tipo': 'NUMBER', 'permissao_padrao': 'consulta_preco'}]
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=catalogo):
            self.assertEqual(self.client.get('/api/product-fields/catalog').json()['colunas'], catalogo)
            resposta = self.client.put('/api/product-fields', headers=headers, json={'campos': [{'coluna': 'CODAUXILIAR'}]})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['campos'], [{'coluna': 'CODAUXILIAR', 'permissao': 'consulta_preco'}])
        self.assertTrue(permissoes.ARQUIVO_DADOS.with_name('campos_produto.json').exists())
        previa = self.client.post('/api/message-templates/preview', headers=headers,
            json={'id': 'produto', 'texto': 'EAN: {codauxiliar}'})
        self.assertEqual(previa.status_code, 200)
        self.assertIn('7891234567890', previa.json()['texto'])
        resposta = self.client.put('/api/message-templates', headers=headers, json={'templates': {'produto': 'EAN: {codauxiliar}'}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.client.put('/api/product-fields', headers=headers, json={'campos': []}).status_code, 400)

    def test_campos_invalidos_nao_chegam_ao_oracle(self):
        headers = {'X-CSRF-Token': self.csrf}
        with patch.object(painel_admin, 'listar_colunas_produto') as listar:
            for corpo in ([], {'campos': 'CODAUXILIAR'}, {'campos': [{'coluna': 'P.CODAUXILIAR'}]},
                          {'campos': [{'coluna': 'CODAUXILIAR', 'permissao': 'admin'}]}):
                with self.subTest(corpo=corpo):
                    self.assertEqual(self.client.put('/api/product-fields', headers=headers, json=corpo).status_code, 400)
        listar.assert_not_called()

    def test_catalogo_indisponivel_preserva_configuracao_salva(self):
        headers = {'X-CSRF-Token': self.csrf}
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[{'coluna': 'CODAUXILIAR'}]):
            self.client.put('/api/product-fields', headers=headers, json={'campos': [{'coluna': 'CODAUXILIAR'}]})
        with patch.object(painel_admin, 'listar_colunas_produto', side_effect=RuntimeError('indisponível')):
            self.assertEqual(self.client.get('/api/product-fields/catalog').status_code, 503)
            resposta = self.client.get('/api/product-fields')
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.json()['campos'][0]['coluna'], 'CODAUXILIAR')
            self.assertEqual(self.client.put('/api/product-fields', headers=headers, json={'campos': [{'coluna': 'CODEPTO'}]}).status_code, 503)
        self.assertEqual(self.client.get('/api/product-fields').json(), resposta.json())

    def test_campo_ausente_no_catalogo_nao_e_salvo(self):
        with patch.object(painel_admin, 'listar_colunas_produto', return_value=[]):
            resposta = self.client.put('/api/product-fields', headers={'X-CSRF-Token': self.csrf},
                json={'campos': [{'coluna': 'CODAUXILIAR'}]})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(permissoes.ARQUIVO_DADOS.with_name('campos_produto.json').exists())

    def test_personalizacao_exige_login_e_csrf(self):
        anonimo = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        self.assertEqual(anonimo.get('/api/message-templates').status_code, 401)
        self.assertEqual(anonimo.put('/api/message-templates', json={'templates': {'produto': 'Teste'}}).status_code, 401)
        self.assertEqual(self.client.put('/api/message-templates', json={'templates': {'produto': 'Teste'}}).status_code, 403)
        self.assertEqual(self.client.post('/api/message-templates/preview', json={'id': 'produto', 'texto': 'Teste'}).status_code, 403)

    def test_personalizacao_salva_previsualiza_e_restaura(self):
        headers = {'X-CSRF-Token': self.csrf}
        resposta = self.client.get('/api/message-templates')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('produto', [modelo['id'] for modelo in resposta.json()['templates']])
        previa = self.client.post('/api/message-templates/preview', headers=headers,
            json={'id': 'produto', 'texto': 'Minha loja: {descricao} / {codprod}'})
        self.assertEqual(previa.status_code, 200)
        self.assertIn('PRODUTO DE EXEMPLO / 1663', previa.json()['texto'])
        self.assertFalse(permissoes.ARQUIVO_DADOS.with_name('mensagens.json').exists())
        resposta = self.client.put('/api/message-templates', headers=headers,
            json={'templates': {'produto': 'Minha loja: {descricao}'}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(permissoes.obter_mensagens_personalizadas()['produto'], 'Minha loja: {descricao}')
        resposta = self.client.put('/api/message-templates', headers=headers, json={'templates': {'produto': None}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(permissoes.obter_mensagens_personalizadas(), {})

    def test_personalizacao_rejeita_campos_restritos_e_corpos_invalidos(self):
        headers = {'X-CSRF-Token': self.csrf}
        for corpo in ([], {'templates': []}, {'templates': {'preco': '{custo}'}}, {'templates': {'produto': ''}}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.put('/api/message-templates', headers=headers, json=corpo).status_code, 400)
        for corpo in ({'id': [], 'texto': 'Teste'}, {'id': 'preco', 'texto': '{programado}'}, []):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post('/api/message-templates/preview', headers=headers, json=corpo).status_code, 400)

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.arquivo_original = permissoes.ARQUIVO_DADOS
        self.legado_original = permissoes.ARQUIVO_LEGADO
        permissoes.ARQUIVO_DADOS = Path(self.tempdir.name) / "dados_bot.json"
        permissoes.ARQUIVO_LEGADO = Path(self.tempdir.name) / "modulos.permissoes.db"
        permissoes.inicializar()
        permissoes.registrar_usuario(123, "Pessoa", "pessoa")
        painel_admin._tentativas_login.clear()
        from modulos.seguranca import ProtecaoHTTP
        camada = app.middleware_stack
        while camada is not None:
            if isinstance(camada, ProtecaoHTTP):
                camada.taxa.registros.clear()
            camada = getattr(camada, 'app', None)
        self.client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        resposta = self.client.post(
            "/api/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.csrf = resposta.json()["csrf"]

    def tearDown(self):
        permissoes.ARQUIVO_DADOS = self.arquivo_original
        permissoes.ARQUIVO_LEGADO = self.legado_original
        self.tempdir.cleanup()

    def test_login_e_atualizacao_de_perfil(self):
        resposta = self.client.put(
            "/api/users/123",
            headers={"X-CSRF-Token": self.csrf},
            json={
                "aprovado": True,
                "consulta_preco": True,
                "buscar_codauxiliar2": True,
                "ver_margem_produto": True,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(permissoes.tem_permissao(123, "buscar_codauxiliar2"))
        self.assertTrue(permissoes.tem_permissao(123, "ver_margem_produto"))
        self.assertFalse(permissoes.tem_permissao(123, "ver_custos"))

    def test_edicao_sem_csrf_e_negada(self):
        resposta = self.client.put("/api/users/123", json={"aprovado": True})
        self.assertEqual(resposta.status_code, 403)

    def test_api_de_usuarios_exige_login(self):
        cliente = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        resposta = cliente.get("/api/users")
        self.assertEqual(resposta.status_code, 401)

    def test_admin_edita_proprio_acesso_sem_perder_painel(self):
        headers = {'X-CSRF-Token': self.csrf}
        resposta = self.client.put('/api/users/999', headers=headers, json={'aprovado': False})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json()['aprovado'])
        self.assertFalse(permissoes.tem_permissao(999, 'consulta_preco'))
        self.assertEqual(self.client.get('/api/settings').status_code, 200)
        self.assertEqual(self.client.get('/api/users').status_code, 200)
        resposta = self.client.put('/api/users/999', headers=headers,
            json={'aprovado': True, 'consulta_preco': True, 'ver_custos': False})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(permissoes.tem_permissao(999, 'consulta_preco'))
        self.assertFalse(permissoes.tem_permissao(999, 'ver_custos'))

    def test_catalogo_filiais_regioes_exige_login_e_consulta_oracle(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get('/api/access-options').status_code, 401)
        dados = {'filiais_permitidas': [{'codigo': '1', 'nome': 'Filial 1'}],
                 'tabelas_permitidas': [{'codigo': '2', 'nome': 'VAREJO', 'ativa': True}]}
        with patch('modulos.painel_admin.listar_opcoes_acesso', return_value=dados):
            resposta = self.client.get('/api/access-options')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), dados)
        with patch('modulos.painel_admin.listar_opcoes_acesso', side_effect=RuntimeError('falha')):
            self.assertEqual(self.client.get('/api/access-options').status_code, 503)

    def test_modelo_propaga_filiais_e_tabelas(self):
        headers = {'X-CSRF-Token': self.csrf}
        self.client.get('/api/profile-templates')
        dados = {'nome': 'Cliente', 'permissoes': {'consulta_preco': True},
                 'filiais_permitidas': ['1'], 'tabelas_permitidas': ['2']}
        self.assertEqual(self.client.put('/api/profile-templates/cliente', headers=headers, json=dados).status_code, 200)
        resposta = self.client.put('/api/users/123', headers=headers,
            json={'aprovado': True, 'modelo_perfil_id': 'cliente'})
        self.assertEqual(resposta.json()['filiais_permitidas'], ['1'])
        self.client.put('/api/profile-templates/cliente', headers=headers,
            json={'nome': 'Cliente', 'permissoes': {'consulta_preco': True}})
        self.assertEqual(permissoes.obter_perfil(123)['filiais_permitidas'], ['1'])
        self.assertEqual(permissoes.obter_perfil(123)['tabelas_permitidas'], ['2'])
        dados['tabelas_permitidas'] = []
        self.client.put('/api/profile-templates/cliente', headers=headers, json=dados)
        self.assertEqual(permissoes.obter_perfil(123)['tabelas_permitidas'], [])
        resposta = self.client.put('/api/users/123', headers=headers,
            json={'modelo_perfil_id': None, 'filiais_permitidas': '1,2'})
        self.assertEqual(resposta.status_code, 400)

    def test_id_do_admin_nao_cria_perfil_de_teste(self):
        resposta = self.client.post('/api/users', headers={'X-CSRF-Token': self.csrf},
                                   json={'telegram_id': '999', 'nome': 'Administrador'})
        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(resposta.json()['administrador'])
        self.assertTrue(all(resposta.json()[chave] for chave in permissoes.PERMISSOES))
        self.assertEqual(permissoes.listar_perfis_teste()['profiles'], [])

    def test_modelos_perfil_crud_e_permissoes(self):
        headers = {'X-CSRF-Token': self.csrf}
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get('/api/profile-templates').status_code, 401)
        self.assertEqual(self.client.post('/api/profile-templates', json={}).status_code, 403)
        iniciais = self.client.get('/api/profile-templates').json()
        self.assertEqual({m['nome'] for m in iniciais}, {'Funcionário', 'Cliente'})
        self.assertTrue(all(not m['permissoes']['ver_custos'] for m in iniciais))
        resposta = self.client.post('/api/profile-templates', headers=headers,
            json={'nome': 'Vendedor', 'permissoes': {'consulta_preco': True}})
        self.assertEqual(resposta.status_code, 201)
        modelo = next(m for m in resposta.json() if m['nome'] == 'Vendedor')
        self.assertFalse(modelo['permissoes']['ver_preco_programado'])
        resposta = self.client.put('/api/profile-templates/' + modelo['id'], headers=headers,
            json={'nome': 'Vendedor', 'permissoes': {'buscar_codprod': True}})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(permissoes.obter_perfil(123)['aprovado'])
        resposta = self.client.delete('/api/profile-templates/' + modelo['id'], headers=headers)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(any(m['id'] == modelo['id'] for m in resposta.json()))

    def test_modelos_invalidos_nao_sao_salvos(self):
        for dados in ({'nome': '', 'permissoes': {}},
                      {'nome': 'Outro', 'permissoes': {'ver_custos': 'sim'}},
                      {'nome': 'Outro', 'permissoes': {'aprovado': True}}):
            resposta = self.client.post('/api/profile-templates', headers={'X-CSRF-Token': self.csrf}, json=dados)
            self.assertEqual(resposta.status_code, 400)

    def test_modelo_vinculado_propaga_e_respeita_bloqueio(self):
        headers = {'X-CSRF-Token': self.csrf}
        self.client.get('/api/profile-templates')
        resposta = self.client.put('/api/users/123', headers=headers,
            json={'modelo_perfil_id': 'cliente', 'aprovado': True})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['consulta_preco'])
        self.client.put('/api/profile-templates/cliente', headers=headers,
            json={'nome': 'Cliente', 'permissoes': {'ver_preco_programado': True}})
        self.assertTrue(permissoes.tem_permissao(123, 'ver_preco_programado'))
        self.assertFalse(permissoes.tem_permissao(123, 'consulta_preco'))
        self.client.put('/api/users/123', headers=headers, json={'aprovado': False})
        self.assertTrue(all(not permissoes.obter_perfil(123)[chave] for chave in permissoes.PERMISSOES))
        self.client.put('/api/profile-templates/cliente', headers=headers,
            json={'nome': 'Cliente', 'permissoes': {chave: True for chave in permissoes.PERMISSOES}})
        perfil = permissoes.obter_perfil(123)
        self.assertFalse(perfil['aprovado'])
        self.assertTrue(all(not perfil[chave] for chave in permissoes.PERMISSOES))

    def test_remover_vinculo_preserva_permissoes_e_modelo_invalido_e_rejeitado(self):
        headers = {'X-CSRF-Token': self.csrf}
        self.client.get('/api/profile-templates')
        self.client.put('/api/users/123', headers=headers, json={'modelo_perfil_id': 'cliente', 'aprovado': True})
        self.client.put('/api/users/123', headers=headers, json={'modelo_perfil_id': None})
        self.client.put('/api/profile-templates/cliente', headers=headers,
            json={'nome': 'Cliente', 'permissoes': {}})
        self.assertTrue(permissoes.tem_permissao(123, 'consulta_preco'))
        resposta = self.client.put('/api/users/123', headers=headers, json={'modelo_perfil_id': []})
        self.assertEqual(resposta.status_code, 400)

    def test_alterar_permissoes_preserva_aprovacao_mesmo_apos_novo_acesso(self):
        permissoes.atualizar_perfil(123, {'aprovado': True, 'consulta_preco': True})
        headers = {'X-CSRF-Token': self.csrf}
        for valores in ({'consulta_preco': False, 'ver_custos': False},
                        {'consulta_preco': True, 'buscar_codprod': True}):
            resposta = self.client.put('/api/users/123', headers=headers, json=valores)
            self.assertEqual(resposta.status_code, 200)
            self.assertTrue(resposta.json()['aprovado'])
            self.assertTrue(permissoes.registrar_usuario(123)['aprovado'])
        resposta = self.client.put('/api/users/123', headers=headers, json={'aprovado': False})
        self.assertFalse(resposta.json()['aprovado'])

    def test_indicadores_de_conexao_exigem_login(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get('/api/connections').status_code, 401)

    def test_indicadores_distinguem_telegram_ok_e_oracle_sem_acesso(self):
        with patch('modulos.painel_admin._verificar_telegram', new_callable=AsyncMock, return_value={'status': 'connected', 'message': 'conectado'}) as telegram, patch('modulos.painel_admin._verificar_oracle', new_callable=AsyncMock, return_value={'status': 'insufficient_access', 'message': 'Sem acesso às tabelas'}) as oracle:
            resposta = self.client.get('/api/connections')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers['cache-control'], 'no-store')
        self.assertEqual(resposta.json()['checks']['telegram']['status'], 'connected')
        self.assertEqual(resposta.json()['checks']['oracle']['status'], 'insufficient_access')
        telegram.assert_awaited_once()
        oracle.assert_awaited_once()

    def test_salvar_secao_bot_nao_modifica_nem_testa_oracle(self):
        permissoes.salvar_configuracoes({'ORACLE_PASSWORD': 'preservada'})
        with patch('modulos.painel_admin._verificar_telegram', new_callable=AsyncMock, return_value={'status': 'connected'}) as telegram, patch('modulos.painel_admin._verificar_oracle', new_callable=AsyncMock) as oracle:
            resposta = self.client.put('/api/settings', headers={'X-CSRF-Token': self.csrf},
                                      json={'section': 'bot', 'settings': {'TELEGRAM_ADMIN_ID': '999'}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(set(resposta.json()['checks']), {'telegram'})
        telegram.assert_awaited_once()
        oracle.assert_not_awaited()
        self.assertEqual(permissoes.obter_configuracao()['ORACLE_PASSWORD'], 'preservada')

    def test_salvar_secao_oracle_nao_modifica_nem_testa_bot(self):
        permissoes.salvar_configuracoes({'TELEGRAM_BOT_TOKEN': 'preservado'})
        with patch('modulos.painel_admin._verificar_oracle', new_callable=AsyncMock, return_value={'status': 'connected'}) as oracle, patch('modulos.painel_admin._verificar_telegram', new_callable=AsyncMock) as telegram:
            resposta = self.client.put('/api/settings', headers={'X-CSRF-Token': self.csrf},
                                      json={'section': 'oracle', 'settings': {'ORACLE_HOST': '192.0.2.1'}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(set(resposta.json()['checks']), {'oracle'})
        oracle.assert_awaited_once()
        telegram.assert_not_awaited()
        self.assertEqual(permissoes.obter_configuracao()['TELEGRAM_BOT_TOKEN'], 'preservado')

    def test_remover_usuario_exige_autenticacao_csrf_e_preserva_admin(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).delete('/api/users/123').status_code, 401)
        self.assertEqual(self.client.delete('/api/users/123').status_code, 403)
        headers = {'X-CSRF-Token': self.csrf}
        permissoes.registrar_usuario(999, 'Admin')
        self.assertEqual(self.client.delete('/api/users/999', headers=headers).status_code, 400)
        self.assertEqual(self.client.delete('/api/users/123', headers=headers).status_code, 204)
        self.assertIsNone(permissoes.obter_perfil(123))
        self.assertEqual(self.client.delete('/api/users/123', headers=headers).status_code, 404)

    def test_remover_perfil_ativo_restaura_admin(self):
        headers = {'X-CSRF-Token': self.csrf}
        criado = self.client.post('/api/test-profiles', headers=headers,
                                  json={'action': 'criar', 'nome': 'Teste'}).json()
        perfil_id = criado['profiles'][0]['id']
        self.client.post('/api/test-profiles', headers=headers,
                         json={'action': 'ativar', 'id': perfil_id})
        self.assertFalse(permissoes.eh_admin_bot(999))
        resposta = self.client.post('/api/test-profiles', headers=headers,
                                    json={'action': 'remover', 'id': perfil_id})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['profiles'], [])
        self.assertIsNone(resposta.json()['active'])
        self.assertTrue(permissoes.eh_admin_bot(999))

    def test_permissao_de_impressao_foi_removida(self):
        resposta = self.client.put('/api/users/123', headers={'X-CSRF-Token': self.csrf},
                                  json={'imprimir': True})
        self.assertEqual(resposta.status_code, 400)
        self.assertNotIn('["imprimir",', painel_admin.PAGINA)

    def test_cadastrar_usuario_pendente_e_permitir_acesso(self):
        resposta = self.client.post('/api/users', headers={'X-CSRF-Token': self.csrf},
                                   json={'telegram_id': '456', 'nome': 'Novo usuário'})
        self.assertEqual(resposta.status_code, 201)
        self.assertFalse(resposta.json()['aprovado'])
        self.assertFalse(permissoes.tem_permissao(456, 'consulta_preco'))
        resposta = self.client.put('/api/users/456', headers={'X-CSRF-Token': self.csrf},
                                  json={'aprovado': True, 'consulta_preco': True})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(permissoes.tem_permissao(456, 'consulta_preco'))

    def test_cadastro_exige_login_csrf_e_id_valido(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).post('/api/users', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/users', json={}).status_code, 403)
        for identificador in ('0', '-1', True, 'abc', None):
            resposta = self.client.post('/api/users', headers={'X-CSRF-Token': self.csrf},
                                       json={'telegram_id': identificador})
            self.assertEqual(resposta.status_code, 400)

    def test_cadastro_duplicado_nao_altera_perfil(self):
        resposta = self.client.post('/api/users', headers={'X-CSRF-Token': self.csrf},
                                   json={'telegram_id': '123', 'nome': 'Outro'})
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(permissoes.obter_perfil(123)['nome'], 'Pessoa')

    def test_perfis_teste_independentes_e_ativacao(self):
        permissoes.registrar_usuario(999, 'Original')
        for nome in ('Consulta', 'Impressao'):
            resposta = self.client.post('/api/test-profiles', headers={'X-CSRF-Token': self.csrf},
                                       json={'action': 'criar', 'nome': nome})
            self.assertEqual(resposta.status_code, 200)
        self.assertEqual(permissoes.obter_perfil(999)['nome'], 'Original')
        data = self.client.get('/api/test-profiles').json()
        self.assertEqual(len(data['profiles']), 2)
        self.assertIsNone(data['active'])
        perfil_id = data['profiles'][0]['id']
        headers = {'X-CSRF-Token': self.csrf}
        resposta = self.client.post('/api/test-profiles', headers=headers, json={
            'action': 'salvar', 'id': perfil_id,
            'permissions': {'aprovado': True, 'consulta_preco': True, 'buscar_codprod': True}})
        self.assertEqual(resposta.status_code, 200)
        resposta = self.client.post('/api/test-profiles', headers=headers,
                                   json={'action': 'ativar', 'id': perfil_id})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(permissoes.eh_admin_bot(999))
        self.assertTrue(permissoes.tem_permissao(999, 'buscar_codprod'))
        self.assertFalse(permissoes.tem_permissao(999, 'ver_custos'))
        self.assertTrue(permissoes.eh_admin(999))
        self.assertEqual(self.client.get('/api/users').status_code, 200)
        self.client.post('/api/test-profiles', headers=headers, json={
            'action': 'salvar', 'id': perfil_id, 'permissions': {'aprovado': False}})
        self.assertFalse(permissoes.tem_permissao(999, 'consulta_preco'))
        self.assertFalse(permissoes.perfil_teste_ativo(999)['aprovado'])
        self.client.post('/api/test-profiles', headers=headers, json={'action': 'ativar', 'id': None})
        self.assertTrue(permissoes.eh_admin_bot(999))
        self.assertTrue(permissoes.tem_permissao(999, 'ver_custos'))

    def test_perfis_teste_validam_acesso_e_campos(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get('/api/test-profiles').status_code, 401)
        self.assertEqual(self.client.post('/api/test-profiles', json={}).status_code, 403)
        for body in ({'action': 'ativar', 'id': 'missing'},
                     {'action': 'salvar', 'id': []}, {'action': 'criar'}, []):
            resposta = self.client.post('/api/test-profiles', headers={'X-CSRF-Token': self.csrf}, json=body)
            self.assertEqual(resposta.status_code, 400)

    def test_health_independe_de_telegram_e_oracle(self):
        resposta = self.client.get("/health")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok"})

    def test_seletor_de_pastas_exige_login(self):
        self.assertEqual(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)).get("/api/directories").status_code, 401)

    def test_seletor_lista_apenas_pastas_e_permite_voltar(self):
        raiz = Path(self.tempdir.name).resolve()
        (raiz / "instantclient").mkdir()
        (raiz / "arquivo.txt").write_text("teste", encoding="utf-8")
        resposta = self.client.get("/api/directories", params={"path": str(raiz)})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {
            "path": str(raiz), "parent": str(raiz.parent),
            "directories": [{"name": "instantclient", "path": str(raiz / "instantclient")}],
        })

    def test_seletor_rejeita_caminhos_invalidos_e_arquivos(self):
        arquivo = Path(self.tempdir.name) / "arquivo.txt"
        arquivo.write_text("teste", encoding="utf-8")
        for caminho in ("relativo", str(arquivo), str(arquivo / "inexistente")):
            with self.subTest(caminho=caminho):
                resposta = self.client.get("/api/directories", params={"path": caminho})
                self.assertEqual(resposta.status_code, 400)

    def test_trocar_senha_persiste_e_encerra_sessoes_antigas(self):
        outra_sessao = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        resposta = outra_sessao.post(
            "/api/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(resposta.status_code, 200)

        alteracao = self.client.post(
            "/api/change-password",
            headers={"X-CSRF-Token": self.csrf},
            json={
                "current_password": "admin",
                "new_password": "uma-senha-nova-segura-2026",
            },
        )
        self.assertEqual(alteracao.status_code, 200)
        self.csrf = alteracao.json()["csrf"]

        self.assertEqual(self.client.get("/api/users").status_code, 200)
        self.assertEqual(outra_sessao.get("/api/users").status_code, 401)

        nova_sessao = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        resposta = nova_sessao.post(
            "/api/login",
            json={
                "username": "admin",
                "password": "uma-senha-nova-segura-2026",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            nova_sessao.post(
                "/api/login",
                json={"username": "admin", "password": "admin"},
            ).status_code,
            401,
        )

    def test_troca_de_senha_rejeita_senha_atual_incorreta(self):
        resposta = self.client.post(
            "/api/change-password",
            headers={"X-CSRF-Token": self.csrf},
            json={
                "current_password": "senha-errada",
                "new_password": "uma-senha-nova-segura-2026",
            },
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.client.get("/api/users").status_code, 200)

    def test_configuracoes_sao_salvas_em_json_e_segredos_nao_sao_retornados(self):
        with (
            patch(
                "modulos.painel_admin._verificar_telegram",
                new_callable=AsyncMock,
                return_value={"status": "connected", "message": "conectado"},
            ),
            patch(
                "modulos.painel_admin._verificar_oracle",
                new_callable=AsyncMock,
                return_value={"status": "unavailable", "message": "sem acesso"},
            ),
        ):
            resposta = self.client.put(
                "/api/settings",
                headers={"X-CSRF-Token": self.csrf},
                json={
                    "settings": {
                        "TELEGRAM_ADMIN_ID": "123456789",
                        "TELEGRAM_BOT_TOKEN": "token-ficticio",
                        "ORACLE_HOST": "192.0.2.10",
                        "ORACLE_PORT": "1521",
                        "ORACLE_PASSWORD": "senha-ficticia",
                    }
                },
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("token-ficticio", resposta.text)
        self.assertNotIn("senha-ficticia", resposta.text)
        self.assertEqual(
            resposta.json()["checks"],
            {
                "telegram": {"status": "connected", "message": "conectado"},
                "oracle": {"status": "unavailable", "message": "sem acesso"},
            },
        )

        configuracoes = self.client.get("/api/settings")
        self.assertEqual(configuracoes.status_code, 200)
        self.assertTrue(configuracoes.json()["TELEGRAM_BOT_TOKEN_configured"])
        self.assertTrue(configuracoes.json()["ORACLE_PASSWORD_configured"])
        self.assertTrue(configuracoes.json()["BOT_DATA_DIR"])
        self.assertNotEqual(
            configuracoes.json()["TELEGRAM_BOT_TOKEN"], "token-ficticio"
        )

        dados = json.loads(
            permissoes.ARQUIVO_DADOS.read_text(encoding="utf-8")
        )
        self.assertEqual(
            json.loads(permissoes.ARQUIVO_DADOS.with_name('config_bot.json').read_text(encoding='utf-8'))["TELEGRAM_BOT_TOKEN"], "token-ficticio"
        )
        self.assertEqual(
            permissoes.obter_configuracao()["ORACLE_PASSWORD"], "senha-ficticia"
        )

    def test_falhas_nos_testes_de_conexao_nao_impedem_salvar_configuracoes(self):
        with (
            patch(
                "modulos.painel_admin._verificar_telegram",
                new_callable=AsyncMock,
                return_value={"status": "unavailable", "message": "sem resposta"},
            ),
            patch(
                "modulos.painel_admin._verificar_oracle",
                new_callable=AsyncMock,
                return_value={"status": "unavailable", "message": "sem acesso"},
            ),
        ):
            resposta = self.client.put(
                "/api/settings",
                headers={"X-CSRF-Token": self.csrf},
                json={"settings": {"TELEGRAM_BOT_TOKEN": "token-ficticio"}},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            permissoes.obter_configuracao()["TELEGRAM_BOT_TOKEN"],
            "token-ficticio",
        )
        self.assertEqual(resposta.json()["checks"]["telegram"]["status"], "unavailable")
        self.assertEqual(resposta.json()["checks"]["oracle"]["status"], "unavailable")

    def test_teste_telegram_valida_token_com_get_me(self):
        bot = AsyncMock()
        bot.__aenter__.return_value = bot
        with patch("modulos.painel_admin.Bot", return_value=bot):
            resultado = asyncio.run(
                painel_admin._verificar_telegram(
                    {"TELEGRAM_BOT_TOKEN": "token-nao-exibido"}
                )
            )

        self.assertEqual(resultado["status"], "connected")
        bot.get_me.assert_awaited_once()

    def test_teste_telegram_identifica_token_recusado(self):
        bot = AsyncMock()
        bot.__aenter__.return_value = bot
        bot.get_me.side_effect = InvalidToken("token inválido")
        with patch("modulos.painel_admin.Bot", return_value=bot):
            resultado = asyncio.run(
                painel_admin._verificar_telegram(
                    {"TELEGRAM_BOT_TOKEN": "token-nao-exibido"}
                )
            )

        self.assertEqual(resultado["status"], "invalid_token")
        self.assertNotIn("token-nao-exibido", str(resultado))

    def test_teste_oracle_executa_sonda_de_conexao(self):
        configuracao = {
            "ORACLE_HOST": "db.exemplo.local",
            "ORACLE_SERVICE": "WINTHOR",
            "ORACLE_USER": "bot",
            "ORACLE_PASSWORD": "senha-ficticia",
        }
        with patch("modulos.painel_admin.testar_conexao_oracle", return_value=True) as probe:
            resultado = asyncio.run(
                painel_admin._verificar_oracle(configuracao)
            )

        self.assertEqual(resultado["status"], "connected")
        probe.assert_called_once_with()

    def test_api_invalida_porta_fora_do_intervalo(self):
        resposta = self.client.put(
            "/api/settings",
            headers={"X-CSRF-Token": self.csrf},
            json={"settings": {"WEB_ADMIN_PORT": "70000"}},
        )
        self.assertEqual(resposta.status_code, 400)

    def test_status_do_servico_windows_exige_login(self):
        cliente = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))
        resposta = cliente.get("/api/windows-service")
        self.assertEqual(resposta.status_code, 401)

    def test_status_do_servico_windows_e_exibido(self):
        status = {
            "available": True,
            "installed": True,
            "state": "stopped",
            "automatic": True,
        }
        with patch("modulos.painel_admin.obter_status_servico", return_value=status):
            resposta = self.client.get("/api/windows-service")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), status)

    def test_acao_do_servico_windows_exige_csrf(self):
        resposta = self.client.post("/api/windows-service/install")
        self.assertEqual(resposta.status_code, 403)

    def test_acao_do_servico_windows_e_validada_e_encaminhada(self):
        with patch(
            "modulos.painel_admin.solicitar_acao_servico",
            return_value={"message": "Solicitação encaminhada."},
        ) as solicitar:
            resposta = self.client.post(
                "/api/windows-service/install",
                headers={"X-CSRF-Token": self.csrf},
                json={},
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["message"], "Solicitação encaminhada.")
        solicitar.assert_called_once_with("install")

        invalida = self.client.post(
            "/api/windows-service/anything",
            headers={"X-CSRF-Token": self.csrf},
            json={},
        )
        self.assertEqual(invalida.status_code, 400)

    def test_url_do_painel_usa_ip_do_computador(self):
        with patch.dict(os.environ, {
            "WEB_ADMIN_HOST": "0.0.0.0",
            "WEB_ADMIN_PORT": "8765",
            "WEB_ADMIN_URL": "",
        }):
            with patch("modulos.painel_admin.socket.socket") as socket_mock:
                socket_mock.return_value.__enter__.return_value.getsockname.return_value = (
                    "10.20.30.40", 0
                )
                self.assertEqual(
                    painel_admin.obter_url_acesso(),
                    "http://10.20.30.40:8765",
                )


if __name__ == "__main__":
    unittest.main()
