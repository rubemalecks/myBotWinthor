import json
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from modulos import bot, campos_produto, database, mensagens, permissoes


class CamposProdutoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.arquivo = Path(self.temp.name) / 'dados_bot.json'
        self.patch = patch.object(permissoes, 'ARQUIVO_DADOS', self.arquivo)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.catalogo = [{'coluna': 'CODAUXILIAR'}, {'coluna': 'CODAUXILIAR2'}, {'coluna': 'CODEPTO'}]

    def habilitar(self, campos=None):
        return campos_produto.salvar_campos_produto(campos or [{'coluna': 'CODAUXILIAR'}], self.catalogo)

    def test_persiste_so_na_pasta_de_dados_sem_modificar_mensagens(self):
        self.assertEqual(campos_produto.obter_campos_produto(), [])
        self.habilitar()
        salvos = campos_produto.obter_campos_produto(estrito=True)
        self.assertEqual(salvos, [{'coluna': 'CODAUXILIAR', 'permissao': 'consulta_preco'}])
        self.assertEqual(json.loads(self.arquivo.with_name('campos_produto.json').read_text(encoding='utf-8')), {'campos': salvos})
        self.assertFalse(self.arquivo.exists())
        self.assertFalse(self.arquivo.with_name('mensagens.json').exists())

    def test_coluna_habilitada_entra_no_select_e_no_contexto_sem_alterar_busca(self):
        self.habilitar()
        resultado = [{'codprod': 6, 'descricao': 'Teste', 'pvenda': 10, 'nome_tabela': 'VAREJO',
                      'extra_0': Decimal('7891234567890')}]
        with patch.object(database, 'executar_consulta', return_value=resultado) as executar:
            produtos = database.consultar_produto('6001', ('codauxiliar',), {'tabelas_permitidas': ['1']})
        sql, parametros = executar.call_args.args
        self.assertIn('P.CODAUXILIAR AS EXTRA_0', sql)
        self.assertIn('P.CODAUXILIAR = :CODAUXILIAR', sql)
        self.assertIn('P.DTEXCLUSAO IS NULL', sql)
        self.assertIn('T.NUMREGIAO IN (:AC_TAB_0)', sql)
        self.assertEqual(parametros['CODAUXILIAR'], 6001)
        self.assertNotIn('extra_0', produtos[0])
        self.assertEqual(campos_produto.valores_campos_produto(produtos[0])['codauxiliar'], '7891234567890')

    def test_codigo_barras_disponivel_nas_variaveis_e_na_previa(self):
        with self.assertRaises(ValueError):
            mensagens.validar_modelo('produto', '{codauxiliar}')
        self.habilitar()
        modelos = {modelo['id']: modelo for modelo in mensagens.listar_modelos()}
        self.assertIn('codauxiliar', modelos['produto']['exemplo'])
        self.assertIn('codauxiliar', modelos['formula_produto']['exemplo'])
        self.assertNotIn('codauxiliar', modelos['preco']['exemplo'])
        self.assertEqual(mensagens.previa_modelo('produto', 'EAN: {codauxiliar}'), 'EAN: 7891234567890')

    def test_campo_restrito_nao_aparece_para_quem_nao_ve_custos(self):
        self.habilitar([{'coluna': 'CODAUXILIAR'}, {'coluna': 'CODEPTO', 'permissao': 'ver_custos'}])
        mensagens.salvar_modelos({'produto': '{descricao}\nEAN: {codauxiliar}\nDepartamento: {codepto}\n'})
        produto = {'codprod': 6, 'descricao': 'Teste', 'pvenda': 10, 'ptabela': 10,
                   'nome_tabela': 'VAREJO', 'numregiao': 1, 'campos_personalizados': {
                       'codauxiliar': {'valor': '07891234567890', 'permissao': 'consulta_preco'},
                       'codepto': {'valor': 9999, 'permissao': 'ver_custos'}}}
        texto = bot.montar_mensagem_precos([produto])
        self.assertIn('EAN: 07891234567890', texto)
        self.assertIn('Sem permissão', texto)
        self.assertNotIn('9999', texto)
        self.assertIn('Departamento: 9999', bot.montar_mensagem_precos([produto], permissoes_campos={'consulta_preco', 'ver_custos'}))

    def test_nao_remove_campo_ainda_em_uso_em_modelo_salvo(self):
        self.habilitar()
        mensagens.salvar_modelos({'formula_produto': 'EAN: {codauxiliar}'})
        with self.assertRaisesRegex(ValueError, 'Remova as variáveis'):
            mensagens.validar_campos_em_uso([])
        mensagens.salvar_modelos({'formula_produto': None})
        mensagens.validar_campos_em_uso([])
        campos_produto.salvar_campos_produto([], [])
        self.assertEqual(campos_produto.obter_campos_produto(), [])

    def test_nao_aceita_sql_nomes_fixos_colunas_ausentes_ou_permissoes_arbitrarias(self):
        for coluna in ('CODAUXILIAR FROM PCPRODUT--', 'CODAUXILIAR; DROP TABLE X', 'P.CODAUXILIAR',
                       'CODPROD', 'DESCRICAO', 'DTEXCLUSAO', 'codauxiliar', 'COD"AUXILIAR'):
            with self.subTest(coluna=coluna), self.assertRaises(ValueError):
                self.habilitar([{'coluna': coluna}])
        for campos in ('CODAUXILIAR', [{'coluna': 'CODAUXILIAR', 'permissao': True}],
                       [{'coluna': 'CODAUXILIAR', 'permissao': 'admin'}],
                       [{'coluna': 'CODAUXILIAR'}, {'coluna': 'CODAUXILIAR'}],
                       [{'coluna': 'AUSENTE'}], [{'coluna': 'CODAUXILIAR', 'sql': 'SELECT'}]):
            with self.subTest(campos=campos), self.assertRaises(ValueError):
                campos_produto.salvar_campos_produto(campos, self.catalogo)
        self.assertFalse(self.arquivo.with_name('campos_produto.json').exists())

    def test_colunas_desconhecidas_comecam_restritas_e_limite_e_respeitado(self):
        self.assertEqual(campos_produto.validar_campos([{'coluna': 'CAMPO_NOVO'}])[0]['permissao'], 'ver_custos')
        with self.assertRaises(ValueError):
            campos_produto.validar_campos([{'coluna': f'CAMPO_{i}'} for i in range(21)])

    def test_valores_nulos_datas_e_zeros(self):
        resultado = campos_produto.valores_campos_produto({'campos_personalizados': {
            'nulo': {'valor': None, 'permissao': 'consulta_preco'},
            'data': {'valor': datetime(2026, 10, 23), 'permissao': 'consulta_preco'},
            'zero': {'valor': 0, 'permissao': 'consulta_preco'}}})
        self.assertEqual(resultado, {'nulo': 'Não informado', 'data': '23/10/2026', 'zero': '0'})

    def test_arquivo_invalido_nao_pode_injetar_coluna_na_consulta(self):
        self.arquivo.with_name('campos_produto.json').write_text(json.dumps({'campos': [{'coluna': 'CODAUXILIAR; SELECT'}]}), encoding='utf-8')
        with self.assertLogs('modulos.campos_produto', level='WARNING'):
            sql, _ = database._montar_consulta_produto('6')
        self.assertNotIn('EXTRA_0', sql)
        with self.assertRaises(RuntimeError):
            campos_produto.obter_campos_produto(estrito=True)

    def test_catalogo_le_metadados_sem_buscar_produtos_e_omite_binarios(self):
        with patch.object(database, 'conectar') as conectar:
            cursor = conectar.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.description = [('CODPROD', database.oracledb.DB_TYPE_NUMBER),
                ('CODAUXILIAR', database.oracledb.DB_TYPE_NUMBER), ('DTEXCLUSAO', database.oracledb.DB_TYPE_DATE),
                ('FOTO', database.oracledb.DB_TYPE_BLOB), ('CAMPO_TEXTO', database.oracledb.DB_TYPE_VARCHAR)]
            catalogo = database.listar_colunas_produto()
        self.assertEqual([campo['coluna'] for campo in catalogo], ['CAMPO_TEXTO', 'CODAUXILIAR'])
        self.assertEqual(catalogo[0]['permissao_padrao'], 'ver_custos')
        cursor.execute.assert_called_once_with('SELECT * FROM PCPRODUT WHERE 1=0')
        cursor.fetchall.assert_not_called()
