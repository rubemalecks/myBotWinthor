import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from modulos import permissoes


class PermissoesTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.arquivo_original = permissoes.ARQUIVO_DADOS
        self.legado_original = permissoes.ARQUIVO_LEGADO
        permissoes.ARQUIVO_DADOS = Path(self.tempdir.name) / "dados_bot.json"
        permissoes.ARQUIVO_LEGADO = Path(self.tempdir.name) / "modulos.permissoes.db"
        self.admin_env = patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "999"})
        self.admin_env.start()
        permissoes.inicializar()

    def tearDown(self):
        permissoes.ARQUIVO_DADOS = self.arquivo_original
        permissoes.ARQUIVO_LEGADO = self.legado_original
        self.admin_env.stop()
        self.tempdir.cleanup()

    def test_novo_usuario_fica_pendente_e_permissoes_sao_independentes(self):
        perfil = permissoes.registrar_usuario(123, "Pessoa", "pessoa")
        self.assertEqual(perfil["aprovado"], 0)
        self.assertFalse(permissoes.tem_permissao(123, "consulta_preco"))

        permissoes.atualizar_perfil(123, {
            "aprovado": True,
            "consulta_preco": True,
            "buscar_codauxiliar2": True,
            "ver_margem_produto": True,
        })

        self.assertTrue(permissoes.tem_permissao(123, "consulta_preco"))
        self.assertTrue(permissoes.tem_permissao(123, "buscar_codauxiliar2"))
        self.assertTrue(permissoes.tem_permissao(123, "ver_margem_produto"))
        self.assertFalse(permissoes.tem_permissao(123, "buscar_codprod"))
        self.assertFalse(permissoes.tem_permissao(123, "ver_custos"))

    def test_perfil_legado_preserva_acesso_existente(self):
        permissoes.ARQUIVO_DADOS.unlink()
        conexao = sqlite3.connect(permissoes.ARQUIVO_LEGADO)
        try:
            conexao.execute('''
                CREATE TABLE usuarios (
                    telegram_id INTEGER PRIMARY KEY,
                    autorizado_em TEXT NOT NULL,
                    apelido TEXT
                )
            ''')
            conexao.execute(
                "INSERT INTO usuarios VALUES (123, '2025-01-01', 'teste')"
            )
            conexao.commit()
        finally:
            conexao.close()

        permissoes.inicializar()

        self.assertTrue(permissoes.tem_permissao(123, "consulta_preco"))
        self.assertTrue(permissoes.tem_permissao(123, "buscar_por_foto"))
        self.assertTrue(permissoes.tem_permissao(123, "ver_margem_produto"))
        self.assertTrue(permissoes.tem_permissao(123, "ver_custos"))

    def test_usuario_legado_e_preservado_sem_permissao_de_impressao(self):
        permissoes.ARQUIVO_DADOS.unlink()
        conexao = sqlite3.connect(permissoes.ARQUIVO_LEGADO)
        try:
            conexao.execute('''
                CREATE TABLE usuarios_impressao (
                    telegram_id INTEGER PRIMARY KEY,
                    apelido TEXT,
                    autorizado_em TEXT NOT NULL
                )
            ''')
            conexao.execute(
                "INSERT INTO usuarios_impressao VALUES (123, 'teste', '2025-01-01')"
            )
            conexao.commit()
        finally:
            conexao.close()

        permissoes.inicializar()

        self.assertNotIn("imprimir", permissoes.PERMISSOES)
        with self.assertRaises(ValueError):
            permissoes.tem_permissao(123, "imprimir")
        self.assertTrue(permissoes.tem_permissao(123, "consulta_preco"))
        self.assertFalse(permissoes.tem_permissao(123, "ver_custos"))

    def test_admin_nao_pode_ser_bloqueado(self):
        permissoes.registrar_usuario(999, "Admin")
        with self.assertRaises(ValueError):
            permissoes.atualizar_perfil(999, {"aprovado": False})
        self.assertTrue(permissoes.tem_permissao(999, "ver_custos"))

    def test_preco_programado_exige_permissao_especifica(self):
        permissoes.registrar_usuario(123)
        permissoes.atualizar_perfil(123, {'aprovado': True, 'consulta_preco': True})
        self.assertFalse(permissoes.tem_permissao(123, 'ver_preco_programado'))
        permissoes.atualizar_perfil(123, {'ver_preco_programado': True})
        self.assertTrue(permissoes.tem_permissao(123, 'ver_preco_programado'))

    def test_margens_produto_e_departamento_sao_independentes(self):
        permissoes.registrar_usuario(123)
        permissoes.atualizar_perfil(123, {'aprovado': True, 'ver_margem_produto': True})
        self.assertTrue(permissoes.pode_ver_margem_produto(123))
        self.assertFalse(permissoes.pode_ver_margem_departamento(123))
        permissoes.atualizar_perfil(123, {'ver_margem_produto': False, 'ver_margem_departamento': True})
        self.assertFalse(permissoes.pode_ver_margem_produto(123))
        self.assertTrue(permissoes.pode_ver_margem_departamento(123))

    def test_migracao_margem_antiga_preserva_usuarios_e_perfis_teste(self):
        permissoes.registrar_usuario(123)
        dados = json.loads(permissoes.ARQUIVO_DADOS.read_text(encoding='utf-8'))
        perfil = dados['usuarios']['123']
        perfil.pop('ver_margem_produto')
        perfil.pop('ver_margem_departamento')
        perfil['ver_margem'] = True
        dados['perfis_teste'] = {'teste': {'id': 'teste', 'telegram_id': 999, 'ver_margem': False}}
        permissoes.ARQUIVO_DADOS.write_text(json.dumps(dados), encoding='utf-8')
        permissoes.inicializar()
        migrado = permissoes.obter_perfil(123)
        self.assertTrue(migrado['ver_margem_produto'])
        self.assertTrue(migrado['ver_margem_departamento'])
        self.assertNotIn('ver_margem', migrado)
        teste = permissoes.listar_perfis_teste()['profiles'][0]
        self.assertFalse(teste['ver_margem_produto'])
        self.assertFalse(teste['ver_margem_departamento'])

    def test_campos_de_permissao_invalidos_sao_rejeitados(self):
        permissoes.registrar_usuario(123)
        with self.assertRaises(ValueError):
            permissoes.atualizar_perfil(123, {"sql": True})

    def test_usuarios_e_configuracoes_ficam_persistidos_em_json(self):
        permissoes.registrar_usuario(123, "Pessoa")
        permissoes.salvar_configuracoes({
            "TELEGRAM_ADMIN_ID": "123456789",
            "ORACLE_HOST": "192.0.2.10",
            "ORACLE_PASSWORD": "senha-ficticia",
        })

        dados = json.loads(
            permissoes.ARQUIVO_DADOS.read_text(encoding="utf-8")
        )
        self.assertIn("123", dados["usuarios"])
        bot = json.loads(permissoes.ARQUIVO_DADOS.with_name('config_bot.json').read_text(encoding='utf-8'))
        oracle = json.loads(permissoes.ARQUIVO_DADOS.with_name('config_oracle.json').read_text(encoding='utf-8'))
        self.assertEqual(dados['configuracoes'], {})
        self.assertEqual(bot['TELEGRAM_ADMIN_ID'], '123456789')
        self.assertEqual(oracle['ORACLE_PASSWORD'], 'senha-ficticia')
        self.assertNotIn('ORACLE_PASSWORD', bot)
        self.assertEqual(
            permissoes.obter_configuracao()["ORACLE_PASSWORD"], "senha-ficticia"
        )

    def test_token_do_telegram_nao_e_carregado_do_ambiente(self):
        with patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "token-de-exemplo-nao-utilizar"},
        ):
            configuracoes = permissoes.obter_configuracao()

        self.assertEqual(configuracoes["TELEGRAM_BOT_TOKEN"], "")

    def test_migracao_do_json_unico_preserva_valores(self):
        dados = json.loads(permissoes.ARQUIVO_DADOS.read_text(encoding='utf-8'))
        dados['configuracoes'] = {'TELEGRAM_BOT_TOKEN': 'token-legado', 'ORACLE_PASSWORD': 'senha-legada'}
        permissoes.ARQUIVO_DADOS.write_text(json.dumps(dados), encoding='utf-8')
        for nome in ('config_bot.json', 'config_oracle.json'):
            permissoes.ARQUIVO_DADOS.with_name(nome).unlink(missing_ok=True)
        configuracoes = permissoes.obter_configuracao()
        self.assertEqual(configuracoes['TELEGRAM_BOT_TOKEN'], 'token-legado')
        self.assertEqual(configuracoes['ORACLE_PASSWORD'], 'senha-legada')
        self.assertEqual(json.loads(permissoes.ARQUIVO_DADOS.read_text(encoding='utf-8'))['configuracoes'], {})
        self.assertEqual(permissoes.obter_configuracao(), configuracoes)

    def test_json_separado_invalido_nao_e_sobrescrito(self):
        caminho = permissoes.ARQUIVO_DADOS.with_name('config_oracle.json')
        caminho.write_text('{invalido', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            permissoes.obter_configuracao()
        self.assertEqual(caminho.read_text(encoding='utf-8'), '{invalido')

    def test_migracao_preserva_senha_e_configuracoes_anteriores(self):
        permissoes.ARQUIVO_DADOS.unlink()
        conexao = sqlite3.connect(permissoes.ARQUIVO_LEGADO)
        try:
            conexao.execute('''
                CREATE TABLE usuarios (
                    telegram_id INTEGER PRIMARY KEY,
                    autorizado_em TEXT NOT NULL,
                    aprovado INTEGER NOT NULL,
                    ver_margem INTEGER NOT NULL,
                    ver_custos INTEGER NOT NULL
                )
            ''')
            conexao.execute(
                "INSERT INTO usuarios VALUES (123, '2025-01-01', 1, 1, 0)"
            )
            conexao.execute('''
                CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)
            ''')
            conexao.execute(
                "INSERT INTO configuracoes VALUES ('ORACLE_HOST', 'db.exemplo.local')"
            )
            senha_hash = permissoes._gerar_hash_senha("senha-admin-antiga")
            conexao.execute('''
                CREATE TABLE configuracao_admin (
                    chave TEXT PRIMARY KEY, valor TEXT NOT NULL
                )
            ''')
            conexao.execute(
                "INSERT INTO configuracao_admin VALUES ('senha_hash', ?)", (senha_hash,)
            )
            conexao.execute(
                "INSERT INTO configuracao_admin VALUES ('versao_sessao', '7')"
            )
            conexao.commit()
        finally:
            conexao.close()

        permissoes.inicializar()

        self.assertTrue(permissoes.tem_permissao(123, "ver_margem_produto"))
        self.assertFalse(permissoes.tem_permissao(123, "ver_custos"))
        self.assertEqual(
            permissoes.obter_configuracao()["ORACLE_HOST"], "db.exemplo.local"
        )
        self.assertEqual(permissoes.obter_versao_sessao_admin(), 7)
        self.assertTrue(permissoes.verificar_senha_admin("senha-admin-antiga"))

    def test_gravacoes_concorrentes_mantem_json_valido(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(
                lambda user_id: permissoes.registrar_usuario(user_id),
                range(1000, 1020),
            ))

        dados = json.loads(
            permissoes.ARQUIVO_DADOS.read_text(encoding="utf-8")
        )
        self.assertEqual(len(dados["usuarios"]), 20)


if __name__ == "__main__":
    unittest.main()
