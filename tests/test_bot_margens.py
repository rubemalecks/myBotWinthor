import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from modulos import bot


class MargemNaConsultaTests(unittest.TestCase):
    def test_preco_programado_oculto_por_padrao_e_exibido_com_permissao(self):
        produtos = [{'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                     'ptabela': 12, 'numregiao': 1, 'nome_tabela': 'VAREJO'}]
        sem = bot.montar_mensagem_precos(produtos)
        com = bot.montar_mensagem_precos(produtos, incluir_programado=True)
        self.assertIn('R$ 10,00', sem)
        self.assertNotIn('Programado', sem)
        self.assertNotIn('R$ 12,00', sem)
        self.assertIn('Programado: R$ 12,00', com)

    def test_resumo_calcula_margem_do_mix_sem_expor_custos(self):
        texto = bot.montar_mensagem_margem_departamento([{
            'codepto': 10, 'codfilial': '1', 'nome_tabela': 'VAREJO',
            'total_precos': 100, 'total_custos': 70, 'produtos_validos': 2,
        }])
        self.assertIn('30,00%', texto)
        self.assertIn('Departamento: 10', texto)
        self.assertNotIn('R$', texto)

    def test_consulta_respeita_permissao_e_preserva_preco_em_falha(self):
        produto = {'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                   'ptabela': 10, 'numregiao': 1, 'nome_tabela': 'VAREJO'}
        for permitido, falha in ((False, False), (True, False), (True, True)):
            with self.subTest(permitido=permitido, falha=falha), \
                 patch('modulos.bot.verificar_acesso_consulta', new_callable=AsyncMock, return_value=True), \
                 patch('modulos.bot.tem_permissao', return_value=True), \
                 patch('modulos.bot.consultar_produto', return_value=[produto]), \
                 patch('modulos.bot.pode_ver_custo', return_value=False), \
                 patch('modulos.bot.pode_ver_margem_produto', return_value=False), \
                 patch('modulos.bot.pode_ver_margem_departamento', return_value=permitido), \
                 patch('modulos.bot.consultar_margens_departamento_produto', return_value=[],
                       side_effect=RuntimeError('indisponivel') if falha else None) as consulta, \
                 patch('modulos.bot.enviar_mensagem', new_callable=AsyncMock) as enviar, \
                 patch('modulos.bot.logger'):
                update = MagicMock()
                update.effective_user.id = 123
                asyncio.run(bot.processar_codigo(update, '6'))
                self.assertEqual(consulta.call_count, int(permitido))
                mensagem = enviar.call_args.args[1]
                self.assertIn('R$ 10,00', mensagem)
                self.assertEqual('MARGEM MÉDIA DO DEPARTAMENTO' in mensagem, permitido)


if __name__ == '__main__':
    unittest.main()
