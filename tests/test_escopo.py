import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from modulos import bot, database, margem_departamento
from modulos.escopo import validar_escopo


class EscopoTests(unittest.TestCase):
    def test_validacao_codigos(self):
        self.assertEqual(validar_escopo({'filiais_permitidas': ['01', 2, '1']}), {'filiais_permitidas': ['1', '2']})
        for valor in ('1,2', [True], ['1 OR 1=1'], [-1]):
            with self.assertRaises(ValueError):
                validar_escopo({'tabelas_permitidas': valor})

    def test_precos_so_positivos_e_limites_por_bind(self):
        sql, params = database._montar_consulta_produto('6', ('codprod',),
            {'filiais_permitidas': ['1'], 'tabelas_permitidas': ['2']})
        self.assertIn('T.PVENDA > 0', sql)
        self.assertIn('T.NUMREGIAO IN (:AC_TAB_0)', sql)
        self.assertIn('AF.CODFILIAL IN (:AC_FIL_0)', sql)
        self.assertEqual(params['AC_TAB_0'], 2)
        self.assertEqual(params['AC_FIL_0'], '1')

    def test_lista_vazia_nao_libera_acesso(self):
        sql, _ = database._montar_consulta_produto('6', escopo={'tabelas_permitidas': []})
        self.assertIn('AND 1=0', sql)

    @patch('modulos.margem_departamento.executar_consulta', return_value=[])
    def test_margem_filtra_antes_de_agregar(self, executar):
        margem_departamento.calcular_margens_departamento(10, '1', escopo={'filiais_permitidas': ['2'], 'tabelas_permitidas': ['3']})
        sql, params = executar.call_args.args
        self.assertLess(sql.index('E.CODFILIAL IN (:AC_FIL_0)'), sql.index('GROUP BY'))
        self.assertIn('T.NUMREGIAO IN (:AC_TAB_0)', sql)
        self.assertEqual(params['FILIAL'], '1')
        self.assertEqual(params['AC_FIL_0'], '2')

    def test_distingue_sem_preco_de_inexistente(self):
        for existe in (True, False):
            with patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True), \
                 patch.object(bot, 'tem_permissao', return_value=True), \
                 patch.object(bot, 'obter_escopo_acesso', return_value={}), \
                 patch.object(bot, 'consultar_produto', return_value=[]), \
                 patch.object(bot, 'produto_existe', return_value=existe), patch.object(bot, 'logger'):
                update = MagicMock()
                update.effective_message.reply_text = AsyncMock()
                asyncio.run(bot.processar_codigo(update, '6'))
                texto = update.effective_message.reply_text.call_args.args[0]
                self.assertIn('precificado' if existe else 'não encontrado', texto)
