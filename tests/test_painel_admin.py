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
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.arquivo_original = permissoes.ARQUIVO_DADOS
        self.legado_original = permissoes.ARQUIVO_LEGADO
        permissoes.ARQUIVO_DADOS = Path(self.tempdir.name) / "dados_bot.json"
        permissoes.ARQUIVO_LEGADO = Path(self.tempdir.name) / "modulos.permissoes.db"
        permissoes.inicializar()
        permissoes.registrar_usuario(123, "Pessoa", "pessoa")
        painel_admin._tentativas_login.clear()
        self.client = TestClient(app)
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
        cliente = TestClient(app)
        resposta = cliente.get("/api/users")
        self.assertEqual(resposta.status_code, 401)

    def test_catalogo_filiais_regioes_exige_login_e_consulta_oracle(self):
        self.assertEqual(TestClient(app).get('/api/access-options').status_code, 401)
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
        self.assertEqual(TestClient(app).get('/api/profile-templates').status_code, 401)
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
        self.assertEqual(TestClient(app).get('/api/connections').status_code, 401)

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
        self.assertEqual(TestClient(app).delete('/api/users/123').status_code, 401)
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
        self.assertEqual(TestClient(app).post('/api/users', json={}).status_code, 401)
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
        self.assertEqual(TestClient(app).get('/api/test-profiles').status_code, 401)
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
        self.assertEqual(TestClient(app).get("/api/directories").status_code, 401)

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
        outra_sessao = TestClient(app)
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

        nova_sessao = TestClient(app)
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
        cliente = TestClient(app)
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
