import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from modulos import database, mensagens, permissoes, bot
from modulos.campos_mensagem import preparar_mensagens


class CamposCustosTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        remendo = patch.object(permissoes, 'ARQUIVO_DADOS', Path(pasta.name) / 'dados_bot.json')
        remendo.start()
        self.addCleanup(remendo.stop)

    def test_validacao_salvamento_e_renderizacao(self):
        with patch.object(database, 'listar_colunas_custos', return_value=[{'variavel': 'pcest_custofin'}]):
            textos, _, _ = preparar_mensagens({'custos': 'Financeiro: {PCEST_CUSTOFIN}'})
            mensagens.salvar_modelos(textos)
            with self.assertRaises(ValueError):
                preparar_mensagens({'custos': '{pcest_inexistente}'})
        self.assertEqual(mensagens.renderizar_mensagem('custos', pcest_custofin='R$ 5,00000'), 'Financeiro: R$ 5,00000')
        with self.assertRaises(ValueError):
            preparar_mensagens({'preco': '{pcest_custofin}'})
        for texto in ('{pcest_custofin.__class__}', '{pcest_custofin!r}', '{pcest_custofin:10}'):
            with self.assertRaises(ValueError):
                preparar_mensagens({'custos': texto})

    def test_sql_preserva_binds_escopo_e_exclusao(self):
        with patch.object(database, 'executar_consulta', return_value=[]) as executar:
            database.consultar_custos(6, {'filiais_permitidas': ['2']}, texto='{pcest_custofin}')
        sql, binds = executar.call_args.args
        self.assertIn('E.CUSTOFIN AS PCEST_CUSTOFIN', sql)
        self.assertIn('P.DTEXCLUSAO IS NULL', sql)
        self.assertIn('E.CODFILIAL IN', sql)
        self.assertEqual(binds['CODPROD_PRINCIPAL'], 6)

    def test_bot_formata_campo_por_filial_e_previa_nao_salva(self):
        mensagens.salvar_modelos({'custos': '{filial}: {pcest_custofin}'})
        custos = [{'codfilial': 2, 'custoultent': 3, 'dtultent': None,
                   'numtransent': None, 'pcest_custofin': Decimal('4.12345')}]
        self.assertIn('2: R$ 4,12345', bot.montar_mensagem_custos(custos, []))
        self.assertEqual(mensagens.previa_modelo('custos', '{pcest_outro}', {'pcest_outro': 'Não informado'}), 'Não informado')
        self.assertEqual(permissoes.obter_mensagens_personalizadas()['custos'], '{filial}: {pcest_custofin}')
