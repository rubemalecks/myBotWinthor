import unittest
from unittest.mock import MagicMock, patch

from modulos import iniciar


class IniciarTests(unittest.TestCase):
    def test_ctrl_c_aguarda_encerramento_sem_traceback(self):
        processo = MagicMock()
        processo.wait.side_effect = [KeyboardInterrupt, 0]
        with patch('builtins.print'):
            self.assertEqual(iniciar.aguardar_processo(processo), 0)
        self.assertEqual(processo.wait.call_count, 2)
        processo.terminate.assert_not_called()

    def setUp(self):
        self.config = patch.object(iniciar, 'obter_configuracao', return_value={
            'WEB_ADMIN_PORT': '9000', 'WEB_ADMIN_HOST': '127.0.0.1'})
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_painel_existente_abre_sem_criar_instancia(self):
        with patch.object(iniciar, 'painel_disponivel', return_value=True), \
             patch.object(iniciar.subprocess, 'Popen') as criar, \
             patch.object(iniciar.webbrowser, 'open', return_value=True) as abrir, \
             patch('builtins.print'):
            self.assertEqual(iniciar.iniciar_e_abrir_painel(), 0)
        criar.assert_not_called()
        abrir.assert_called_once_with('http://127.0.0.1:9000', new=2)

    def test_nao_abre_navegador_quando_usuario_recusa(self):
        with patch.object(iniciar, 'painel_disponivel', return_value=True), \
             patch.object(iniciar.webbrowser, 'open') as abrir, patch('builtins.print'):
            self.assertEqual(iniciar.iniciar_e_abrir_painel(abrir_navegador=False), 0)
        abrir.assert_not_called()

    def test_menu_inicia_api_com_ou_sem_navegador(self):
        for resposta, esperado in (('s', True), ('n', False), ('', False)):
            with self.subTest(resposta=resposta), patch('builtins.input', return_value=resposta), \
                 patch.object(iniciar, 'iniciar_e_abrir_painel', return_value=0) as executar, \
                 patch('builtins.print'):
                self.assertEqual(iniciar.main(), 0)
                executar.assert_called_once_with(abrir_navegador=esperado)

    def test_servico_instalado_inicia_antes_de_abrir(self):
        with patch.object(iniciar, 'painel_disponivel', side_effect=[False, True]), \
             patch.object(iniciar, 'obter_status_servico', return_value={'installed': True, 'state': 'stopped'}), \
             patch.object(iniciar, '_iniciar_servico_windows') as executar, \
             patch.object(iniciar.subprocess, 'Popen') as criar, \
             patch.object(iniciar.webbrowser, 'open', return_value=True) as abrir, \
             patch('builtins.print'):
            self.assertEqual(iniciar.iniciar_e_abrir_painel(), 0)
        executar.assert_called_once()
        criar.assert_not_called()
        abrir.assert_called_once()

    def test_sem_servico_executa_bot_e_aguarda_encerramento(self):
        with patch.object(iniciar, 'painel_disponivel', side_effect=[False, True]), \
             patch.object(iniciar, 'obter_status_servico', return_value={'installed': False}), \
             patch.object(iniciar.subprocess, 'Popen') as criar, \
             patch.object(iniciar.webbrowser, 'open', return_value=True), \
             patch('builtins.print'):
            criar.return_value.poll.return_value = None
            criar.return_value.wait.return_value = 0
            self.assertEqual(iniciar.iniciar_e_abrir_painel(), 0)
        self.assertEqual(criar.call_args.args[0][1], str(iniciar.BASE_DIR / 'bot.py'))
        criar.return_value.wait.assert_called_once()

    def test_falha_na_inicializacao_nao_abre_navegador(self):
        with patch.object(iniciar, 'painel_disponivel', return_value=False), \
             patch.object(iniciar, 'obter_status_servico', side_effect=OSError()), \
             patch.object(iniciar.webbrowser, 'open') as abrir, patch('builtins.print'):
            self.assertEqual(iniciar.iniciar_e_abrir_painel(), 1)
        abrir.assert_not_called()

    def test_executavel_ausente_orienta_reparo_sem_criar_outra_instancia(self):
        with patch.object(iniciar, 'painel_disponivel', return_value=False), \
             patch.object(iniciar, 'obter_status_servico', return_value={
                 'installed': True, 'state': 'stopped', 'binary_exists': False,
                 'binary_path': r'C:\Pasta antiga\.venv\pythonservice.exe'}), \
             patch.object(iniciar, '_iniciar_servico_windows') as executar, \
             patch.object(iniciar.subprocess, 'Popen') as criar, \
             patch.object(iniciar.webbrowser, 'open') as abrir, patch('builtins.print') as imprimir:
            self.assertEqual(iniciar.iniciar_e_abrir_painel(), 1)
        executar.assert_not_called()
        criar.assert_not_called()
        abrir.assert_not_called()
        texto = '\n'.join(str(call.args[0]) for call in imprimir.call_args_list)
        self.assertIn('pythonservice.exe', texto)
        self.assertIn('service_helper.py install', texto)

    def test_erros_windows_informam_codigo_e_orientacao_especifica(self):
        for codigo, orientacao in ((2, 'service_helper.py install'), (5, 'Acesso negado'), (1058, 'desativado')):
            erro = OSError()
            erro.winerror = codigo
            erro.strerror = 'Erro simulado do Windows'
            with self.subTest(codigo=codigo), \
                 patch.object(iniciar, 'painel_disponivel', return_value=False), \
                 patch.object(iniciar, 'obter_status_servico', return_value={'installed': True, 'state': 'stopped'}), \
                 patch.object(iniciar, '_iniciar_servico_windows', side_effect=erro), \
                 patch.object(iniciar.webbrowser, 'open') as abrir, patch('builtins.print') as imprimir:
                self.assertEqual(iniciar.iniciar_e_abrir_painel(), 1)
            texto = '\n'.join(str(call.args[0]) for call in imprimir.call_args_list)
            self.assertIn(f'erro Windows {codigo}', texto)
            self.assertIn(orientacao, texto)
            abrir.assert_not_called()
