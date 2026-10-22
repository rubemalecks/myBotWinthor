import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from modulos import bot
from modulos.formulas import explicar_formula


class FormulasTests(unittest.TestCase):
    def test_exibe_substituicao_quando_custos_liberados(self):
        texto = explicar_formula('18.29', '13.59', exibir_valores=True)
        self.assertIn('34,58%', texto)
        self.assertIn('(18,29000 − 13,59000) ÷ 13,59000', texto)

    def test_sem_permissao_oculta_valores_mas_mostra_formula_e_resultado(self):
        texto = explicar_formula('18.29', '13.59')
        self.assertIn('34,58%', texto)
        self.assertIn('Custo de entrada', texto)
        self.assertNotIn('13,59', texto)
        self.assertNotIn('18,29', texto)

    def test_zero_nao_gera_divisao_invalida(self):
        self.assertIn('indisponível', explicar_formula(10, 0))

    def test_usuario_sem_margem_nao_consulta_formula(self):
        update = SimpleNamespace(effective_chat=SimpleNamespace(type='private'),
            effective_user=SimpleNamespace(id=123), effective_message=SimpleNamespace(reply_text=AsyncMock()))
        context = SimpleNamespace(args=['1663'])
        with patch.object(bot, 'verificar_acesso_consulta', new_callable=AsyncMock, return_value=True), \
             patch.object(bot, 'tem_permissao', return_value=False), \
             patch.object(bot, 'consultar_com_log', new_callable=AsyncMock) as consulta:
            asyncio.run(bot.comando_formula(update, context))
            consulta.assert_not_awaited()
            self.assertIn('não permite', update.effective_message.reply_text.call_args.args[0])
