import unittest
from unittest.mock import patch

from modulos import configurar


class ConfigurarTests(unittest.TestCase):
    def test_portas_validas_e_invalidas(self):
        self.assertEqual(configurar.validar_porta('08765'), '8765')
        for valor in ('0', '65536', '-1', 'abc', ''):
            with self.assertRaises(ValueError):
                configurar.validar_porta(valor)

    def test_porta_api_salva_apenas_configuracoes_do_painel(self):
        with patch.object(configurar, 'obter_configuracao', return_value={
            'WEB_ADMIN_PORT': '8765', 'WEB_ADMIN_URL': 'http://servidor:8765'}), \
             patch('builtins.input', side_effect=['9000', 's', 's']), \
             patch.object(configurar, 'salvar_configuracoes') as salvar, patch('builtins.print'):
            configurar.configurar_porta_api()
        salvar.assert_called_once_with({'WEB_ADMIN_PORT': '9000', 'WEB_ADMIN_URL': ''})

    def test_oracle_preserva_senha_vazia_e_nao_altera_bot(self):
        atual = {'ORACLE_HOST': '192.0.2.10', 'ORACLE_PORT': '1521',
                 'ORACLE_SERVICE': 'TESTE', 'ORACLE_USER': 'BOT', 'ORACLE_PASSWORD': 'senha-existente'}
        with patch.object(configurar, 'obter_configuracao', return_value=atual), \
             patch('builtins.input', side_effect=['', '', '', '', 's', 'n']), \
             patch.object(configurar.getpass, 'getpass', return_value=''), \
             patch.object(configurar, 'salvar_configuracoes') as salvar, patch('builtins.print'):
            configurar.configurar_oracle()
        salvo = salvar.call_args.args[0]
        self.assertNotIn('ORACLE_PASSWORD', salvo)
        self.assertTrue(all(chave.startswith('ORACLE_') for chave in salvo))

    def test_cancelamento_nao_salva(self):
        with patch.object(configurar, 'obter_configuracao', return_value={
            'WEB_ADMIN_PORT': '8765', 'WEB_ADMIN_URL': ''}), \
             patch('builtins.input', side_effect=['9000', 'n']), \
             patch.object(configurar, 'salvar_configuracoes') as salvar, patch('builtins.print'):
            configurar.configurar_porta_api()
        salvar.assert_not_called()
