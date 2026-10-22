"""Regressão das consultas com produtos ativos e excluídos no mesmo cadastro."""
import sqlite3
import unittest
from unittest.mock import patch

from modulos import database, margem_departamento


class ProdutosExcluidosTests(unittest.TestCase):
    def setUp(self):
        self.conexao = sqlite3.connect(':memory:')
        self.addCleanup(self.conexao.close)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.create_function('TRUNC', 1, lambda data: data)
        self.conexao.executescript('''
            CREATE TABLE PCPRODUT (
                CODPROD INTEGER, DESCRICAO TEXT, CODAUXILIAR INTEGER,
                CODAUXILIAR2 INTEGER, CODEPTO INTEGER, DTEXCLUSAO TEXT
            );
            CREATE TABLE PCTABPR (CODPROD INTEGER, NUMREGIAO INTEGER, PVENDA REAL, PTABELA REAL);
            CREATE TABLE PCREGIAO (NUMREGIAO INTEGER, REGIAO TEXT, STATUS TEXT);
            CREATE TABLE PCEST (
                CODPROD INTEGER, CODFILIAL TEXT, CUSTOREAL REAL,
                CUSTOULTENT REAL, DTULTENT TEXT
            );
            CREATE TABLE PCMOV (CODPROD INTEGER, NUMTRANSENT INTEGER);
            CREATE TABLE PCNFENT (
                NUMTRANSENT INTEGER, CODFILIAL TEXT, NUMNOTA INTEGER,
                CODFORNEC INTEGER, DTENT TEXT, DTEMISSAO TEXT
            );
            CREATE TABLE PCFORNEC (CODFORNEC INTEGER, FORNECEDOR TEXT);
            INSERT INTO PCPRODUT VALUES (6, 'PRODUTO ATIVO', 6001, 6002, 10, NULL);
            INSERT INTO PCPRODUT VALUES (7, 'PRODUTO EXCLUIDO', 7001, 6, 10, '2026-10-22');
            INSERT INTO PCTABPR VALUES (6, 1, 10, 12), (7, 1, 999, 999), (7, 2, 888, 888);
            INSERT INTO PCREGIAO VALUES (1, 'VAREJO', 'A'), (2, 'ATACADO', 'A');
            INSERT INTO PCEST VALUES (6, '1', 7, 7, NULL), (7, '1', 1000, 1000, NULL), (7, '2', 1000, 1000, NULL);
        ''')
        for modulo in (database, margem_departamento):
            interceptar = patch.object(modulo, 'executar_consulta', side_effect=self.executar_sql)
            interceptar.start()
            self.addCleanup(interceptar.stop)

    def executar_sql(self, sql, parametros):
        # Apenas a limitação Oracle ROWNUM é adaptada; WHEREs, JOINs e agregações
        # são executados contra dados de teste, sem conexão com o Oracle real.
        sql = sql.replace('WHERE ROWNUM <= 11', 'LIMIT 11').replace('AND ROWNUM = 1', 'LIMIT 1')
        return [{chave.lower(): linha[chave] for chave in linha.keys()}
                for linha in self.conexao.execute(sql, parametros).fetchall()]

    def test_busca_por_todos_os_codigos_omite_excluidos_e_preserva_ativos(self):
        for codigo, campos in [('6', None), ('6', ('codprod',)), ('6001', ('codauxiliar',)),
                               ('6002', ('codauxiliar2',)), ('6001', ('codauxiliar', 'codauxiliar2'))]:
            with self.subTest(codigo=codigo, campos=campos):
                self.assertEqual([item['codprod'] for item in database.consultar_produto(codigo, campos)], [6])
        for codigo, campos in [('7', ('codprod',)), ('7001', ('codauxiliar',)), ('6', ('codauxiliar2',))]:
            with self.subTest(codigo=codigo, campos=campos):
                self.assertEqual(database.consultar_produto(codigo, campos), [])

    def test_busca_por_nome_nao_apresenta_excluidos(self):
        self.assertEqual([item['codprod'] for item in database.pesquisar_produtos('PRODUTO')], [6])
        self.assertEqual(database.pesquisar_produtos('EXCLUIDO'), [])

    def test_excluido_nao_e_classificado_como_apenas_sem_preco(self):
        self.assertTrue(database.produto_existe('6', ('codprod',)))
        self.assertFalse(database.produto_existe('7', ('codprod',)))
        self.assertFalse(database.produto_existe('7001', ('codauxiliar',)))

    def test_custos_e_filiais_ignoram_produto_excluido(self):
        self.assertEqual(database.consultar_custos(7), [])
        self.assertEqual(database.listar_filiais_produto(7), [])
        self.assertEqual(database.consultar_custos(6)[0]['custoultent'], 7)
        self.assertEqual(database.listar_filiais_produto(6), [{'codfilial': '1'}])

    def test_opcoes_do_departamento_nao_vem_de_produtos_excluidos(self):
        self.assertEqual(margem_departamento.listar_filiais_departamento(10), [{'codfilial': '1'}])
        self.assertEqual(margem_departamento.listar_regioes_ativas(10), [{'numregiao': 1, 'nome_tabela': 'VAREJO'}])

    def test_totais_e_contagens_do_departamento_ignoram_excluidos(self):
        linhas = margem_departamento.calcular_margens_departamento(10, '1')
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]['total_produtos'], 1)
        self.assertEqual(linhas[0]['produtos_validos'], 1)
        self.assertEqual(linhas[0]['total_precos'], 10)
        self.assertEqual(linhas[0]['total_custos'], 7)
        self.assertEqual(margem_departamento.calcular_margens_departamento(10, '2'), [])

    def test_funcao_complementar_tambem_exige_produto_base_nao_excluido(self):
        self.assertEqual(margem_departamento.consultar_margens_departamento_produto(7), [])
        linhas = margem_departamento.consultar_margens_departamento_produto(6)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]['total_precos'], 10)

    def test_filtro_de_exclusao_preserva_restricoes_de_acesso(self):
        self.assertEqual(database.consultar_produto('6', escopo={'filiais_permitidas': ['2']}), [])
        self.assertEqual(database.consultar_produto('6', escopo={'tabelas_permitidas': ['2']}), [])
        self.assertEqual(database.consultar_custos(6, {'filiais_permitidas': []}), [])
        self.assertEqual(margem_departamento.calcular_margens_departamento(10, '1',
            escopo={'tabelas_permitidas': ['2']}), [])
