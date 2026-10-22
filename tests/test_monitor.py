import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modulos import monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='monitor com espacos ')
        self.addCleanup(self.temp.cleanup)
        self.arquivo = Path(self.temp.name) / 'bot-service.log'

    def test_mostra_cauda_e_apenas_novas_linhas_depois(self):
        self.arquivo.write_text(''.join(f'linha {n}\n' for n in range(3000)), encoding='utf-8')
        leitor = monitor.LeitorLog(self.arquivo, linhas=2)
        self.assertEqual(leitor.ler_novas(), ['linha 2998', 'linha 2999'])
        self.assertEqual(leitor.ler_novas(), [])
        with self.arquivo.open('ab') as arquivo:
            arquivo.write('Nova consulta: usuário de teste\r\n'.encode('utf-8'))
        self.assertEqual(leitor.ler_novas(), ['Nova consulta: usuário de teste'])
        self.assertEqual(leitor.ler_novas(), [])

    def test_zero_ignora_historico_e_acompanha_somente_novos_eventos(self):
        self.arquivo.write_bytes(b'antigo\n')
        leitor = monitor.LeitorLog(self.arquivo, linhas=0)
        self.assertEqual(leitor.ler_novas(), [])
        with self.arquivo.open('ab') as arquivo:
            arquivo.write(b'novo\n')
        self.assertEqual(leitor.ler_novas(), ['novo'])

    def test_aguarda_arquivo_sem_criar_ou_modificar_o_log(self):
        leitor = monitor.LeitorLog(self.arquivo)
        self.assertEqual(leitor.ler_novas(), [])
        self.assertFalse(self.arquivo.exists())
        self.arquivo.write_bytes(b'primeira consulta\n')
        self.assertEqual(leitor.ler_novas(), ['primeira consulta'])
        self.assertEqual(self.arquivo.read_bytes(), b'primeira consulta\n')

    def test_nao_corrompe_utf8_nem_exibe_linha_parcial(self):
        self.arquivo.touch()
        leitor = monitor.LeitorLog(self.arquivo)
        self.assertEqual(leitor.ler_novas(), [])
        linha = 'Consulta João 📦'.encode('utf-8')
        with self.arquivo.open('ab') as arquivo:
            arquivo.write(linha[:-2])
        self.assertEqual(leitor.ler_novas(), [])
        with self.arquivo.open('ab') as arquivo:
            arquivo.write(linha[-2:] + b'\n')
        self.assertEqual(leitor.ler_novas(), ['Consulta João 📦'])

    def test_continua_quando_log_e_truncado_ou_substituido(self):
        self.arquivo.write_bytes(b'consulta antiga bastante longa\n')
        leitor = monitor.LeitorLog(self.arquivo)
        leitor.ler_novas()
        self.arquivo.write_bytes(b'nova\n')
        self.assertEqual(leitor.ler_novas(), ['nova'])
        anterior = self.arquivo.with_suffix('.antigo')
        self.arquivo.rename(anterior)
        self.arquivo.write_bytes(b'outro arquivo\n')
        self.assertEqual(leitor.ler_novas(), ['outro arquivo'])

    def test_filtro_de_consultas_e_ctrl_c_nao_interferem_no_servico(self):
        self.arquivo.write_text('INFO: GET /health 200 OK\nCONSULTA {"usuario_id":123,"codigo":"6"}\n', encoding='utf-8')
        with patch.object(monitor, 'LOG_FILE', self.arquivo), \
             patch.object(monitor.time, 'sleep', side_effect=KeyboardInterrupt), patch('builtins.print') as imprimir:
            self.assertEqual(monitor.main(['--somente-consultas']), 0)
        linhas = [call.args[0] for call in imprimir.call_args_list]
        self.assertIn('CONSULTA {"usuario_id":123,"codigo":"6"}', linhas)
        self.assertNotIn('INFO: GET /health 200 OK', linhas)
        self.assertIn('Monitor encerrado. O serviço permanece em execução.', linhas[-1])
        self.assertTrue(self.arquivo.exists())

    def test_modo_padrao_inclui_requisicoes_http_e_erros(self):
        self.arquivo.write_text('INFO: GET /api/users 200 OK\nORA-00942\n', encoding='utf-8')
        with patch.object(monitor, 'LOG_FILE', self.arquivo), \
             patch.object(monitor.time, 'sleep', side_effect=KeyboardInterrupt), patch('builtins.print') as imprimir:
            self.assertEqual(monitor.main([]), 0)
        linhas = [call.args[0] for call in imprimir.call_args_list]
        self.assertIn('INFO: GET /api/users 200 OK', linhas)
        self.assertIn('ORA-00942', linhas)

    def test_falta_de_permissao_mostra_erro_sem_traceback(self):
        with patch.object(monitor, 'LOG_FILE', self.arquivo), \
             patch.object(monitor.LeitorLog, 'ler_novas', side_effect=PermissionError), patch('builtins.print') as imprimir:
            self.assertEqual(monitor.main([]), 1)
        self.assertIn('permissão de leitura', imprimir.call_args.args[0])

    @unittest.skipUnless(os.name == 'nt', 'Hospedagem do serviço específica do Windows')
    def test_servico_emite_log_utf8_sem_buffer(self):
        from modulos import bot_service
        servico = bot_service.BotWindowsService.__new__(bot_service.BotWindowsService)
        servico.stop_event = object()
        with patch.object(bot_service, 'LOG_FILE', self.arquivo), \
             patch.object(bot_service.servicemanager, 'LogInfoMsg'), \
             patch.object(bot_service.win32event, 'WaitForSingleObject', return_value=bot_service.win32event.WAIT_OBJECT_0), \
             patch.object(bot_service.subprocess, 'Popen') as executar:
            servico.SvcDoRun()
        self.assertIn('-u', executar.call_args.args[0])
        self.assertEqual(executar.call_args.kwargs['env']['PYTHONUTF8'], '1')
        self.assertEqual(executar.call_args.kwargs['env']['PYTHONUNBUFFERED'], '1')
        self.assertEqual(executar.call_args.kwargs['stderr'], bot_service.subprocess.STDOUT)
