import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from modulos import bot


class MargemNaConsultaTests(unittest.TestCase):
    def test_admin_com_acesso_desmarcado_nao_pode_consultar(self):
        update = MagicMock()
        update.effective_user.id = 999
        update.effective_message.reply_text = AsyncMock()
        with patch.object(bot, 'registrar_usuario', new_callable=AsyncMock,
                          return_value={'aprovado': False}), \
             patch.object(bot, 'perfil_teste_ativo', return_value=None), \
             patch.object(bot, 'eh_admin', return_value=True), \
             patch.object(bot, 'registrar_consulta_log'):
            self.assertFalse(asyncio.run(bot.verificar_acesso_consulta(update)))
        update.effective_message.reply_text.assert_awaited_once()

    def test_preco_programado_oculto_por_padrao_e_exibido_com_permissao(self):
        produtos = [{'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                     'ptabela': 12, 'numregiao': 1, 'nome_tabela': 'VAREJO'}]
        sem = bot.montar_mensagem_precos(produtos)
        com = bot.montar_mensagem_precos(produtos, incluir_programado=True)
        self.assertIn('R$ 10,00', sem)
        self.assertNotIn('Programado', sem)
        self.assertNotIn('R$ 12,00', sem)
        self.assertIn('Programado: R$ 12,00', com)

    def test_consulta_individual_mostra_so_lucro_do_produto_e_preserva_preco_em_falha(self):
        produto = {'codprod': 6, 'descricao': 'Produto', 'pvenda': 10,
                   'ptabela': 10, 'numregiao': 1, 'nome_tabela': 'VAREJO'}
        for permitido, falha in ((False, False), (True, False), (True, True)):
            with self.subTest(permitido=permitido, falha=falha), \
                 patch('modulos.bot.verificar_acesso_consulta', new_callable=AsyncMock, return_value=True), \
                 patch('modulos.bot.tem_permissao', return_value=True), \
                 patch('modulos.bot.obter_escopo_acesso', return_value={}), \
                 patch('modulos.bot.obter_opcoes_consulta', return_value={}), \
                 patch('modulos.bot.consultar_produto', return_value=[produto]), \
                 patch('modulos.bot.pode_ver_custo', return_value=False), \
                 patch('modulos.bot.pode_ver_margem_produto', return_value=permitido), \
                 patch('modulos.bot.pode_ver_margem_departamento', return_value=True), \
                 patch('modulos.margem_departamento.consultar_margens_departamento_produto') as departamento, \
                 patch('modulos.bot.consultar_custos', return_value=[{'codfilial': '1', 'custoultent': 7}],
                       side_effect=RuntimeError('indisponivel') if falha else None) as consulta, \
                 patch('modulos.bot.enviar_mensagem', new_callable=AsyncMock) as enviar, \
                 patch('modulos.bot.logger'):
                update = MagicMock()
                update.effective_user.id = 123
                asyncio.run(bot.processar_codigo(update, '6'))
                self.assertEqual(consulta.call_count, int(permitido))
                mensagem = enviar.call_args.args[1]
                self.assertIn('R$ 10,00', mensagem)
                self.assertNotIn('DEPARTAMENTO', mensagem)
                departamento.assert_not_called()
                if permitido and not falha:
                    self.assertIn('MARGEM DO PRODUTO', mensagem)
                    self.assertIn('Lucro presumido sobre o custo: 42,86%', mensagem)
                if not permitido:
                    self.assertNotIn('Lucro presumido', mensagem)
                if falha:
                    self.assertIn('Dados de custo/margem indisponíveis', mensagem)


if __name__ == '__main__':
    unittest.main()
