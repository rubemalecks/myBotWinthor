import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modulos import servico_windows


@unittest.skipUnless(os.name == 'nt', 'Integração específica do Windows')
class ServicoWindowsTests(unittest.TestCase):
    def test_detecta_executavel_ausente_em_caminho_com_espacos(self):
        import win32service
        with tempfile.TemporaryDirectory(prefix='servico com espacos ') as pasta:
            executavel = Path(pasta) / 'pythonservice.exe'
            config = (16, win32service.SERVICE_AUTO_START, 1, f'"{executavel}"')
            with patch('win32serviceutil.QueryServiceStatus', return_value=(16, win32service.SERVICE_STOPPED)), \
                 patch('win32service.OpenSCManager', return_value=1), \
                 patch('win32service.OpenService', return_value=2), \
                 patch('win32service.QueryServiceConfig', return_value=config), \
                 patch('win32service.CloseServiceHandle'):
                estado = servico_windows.obter_status_servico()
                self.assertEqual(estado['binary_path'], str(executavel))
                self.assertFalse(estado['binary_exists'])
                executavel.touch()
                self.assertTrue(servico_windows.obter_status_servico()['binary_exists'])

    def test_reinstalar_atualiza_caminho_do_servico_existente(self):
        from modulos import service_helper
        with tempfile.TemporaryDirectory(prefix='servico com espacos ') as pasta:
            base = Path(pasta)
            executavel = base / 'pythonservice.exe'
            executavel.touch()
            pth = base / 'servico.pth'
            with patch.object(service_helper, 'SITE_PACKAGES', base), \
                 patch.object(service_helper, 'SERVICE_PTH', pth), \
                 patch.object(service_helper.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=True), \
                 patch('win32serviceutil.LocatePythonServiceExe', return_value=str(executavel)), \
                 patch('win32serviceutil.QueryServiceStatus'), \
                 patch('win32serviceutil.InstallService') as instalar, \
                 patch('win32serviceutil.ChangeServiceConfig') as atualizar:
                service_helper.executar('install')
            instalar.assert_not_called()
            self.assertEqual(atualizar.call_args.kwargs['exeName'], str(executavel))
            self.assertTrue(pth.exists())

    def test_nao_registra_servico_com_executavel_ausente(self):
        from modulos import service_helper
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            pth = base / 'servico.pth'
            with patch.object(service_helper, 'SITE_PACKAGES', base), \
                 patch.object(service_helper, 'SERVICE_PTH', pth), \
                 patch.object(service_helper.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=True), \
                 patch('win32serviceutil.LocatePythonServiceExe', return_value=str(base / 'inexistente.exe')), \
                 patch('win32serviceutil.InstallService') as instalar, \
                 patch('win32serviceutil.ChangeServiceConfig') as atualizar:
                with self.assertRaisesRegex(RuntimeError, 'pythonservice.exe'):
                    service_helper.executar('install')
            instalar.assert_not_called()
            atualizar.assert_not_called()
            self.assertFalse(pth.exists())

    def test_banner_bat_nao_interpreta_logo_como_comando_com_lf_ou_crlf(self):
        # O download pode converter as quebras de linha. O BAT contém somente
        # ASCII; o desenho Unicode é responsabilidade do Python.
        raiz = Path(__file__).resolve().parent.parent
        original = (raiz / 'myBotWinthor.bat').read_bytes()
        original.decode('ascii')
        with tempfile.TemporaryDirectory(prefix='banner com espacos ') as pasta:
            arquivo = Path(pasta) / 'banner.bat'
            for quebra in (b'\n', b'\r\n'):
                with self.subTest(quebra=quebra):
                    dados = original.replace(b'\r\n', b'\n').replace(b'\n', quebra)
                    dados = dados.replace(b'%~dp0', (str(raiz) + '\\').encode('utf-8'))
                    arquivo.write_bytes(dados)
                    resultado = subprocess.run(['cmd.exe', '/d', '/c', str(arquivo), '/nopause'],
                        capture_output=True, timeout=15)
                    self.assertEqual(resultado.returncode, 0, resultado.stderr)
                    self.assertEqual(resultado.stderr, b'')
                    self.assertIn(b'my', resultado.stdout)
                    self.assertIn(b'RBTech', resultado.stdout)
