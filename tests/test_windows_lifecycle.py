import json,tempfile,unittest
from pathlib import Path
from desktop.uninstaller import plano,limpar_arquivos
from desktop.windows import PRODUCT,chave_inicio

class LifecycleTests(unittest.TestCase):
    def criar(self,base):
        root=base/'programa';v=root/'versoes'/'v1';v.mkdir(parents=True)
        dados=base/'dados';dados.mkdir()
        (v/'myBotWinthor.exe').write_bytes(b'exe')
        (dados/'dados_bot.json').write_text('{"usuarios":{"1":{}}}')
        (dados/'config_oracle.json').write_text('{"senha":"ficticia"}')
        (dados/'anotacao.txt').write_text('nao remover')
        info={'product':PRODUCT,'install_root':str(root),'data_dir':str(dados),
              'owned_files':['versoes/v1/myBotWinthor.exe','instalacao.json']}
        m=root/'instalacao.json';m.write_text(json.dumps(info))
        return m,root,dados

    def test_desinstalar_preservando_cadastros(self):
        with tempfile.TemporaryDirectory() as d:
            m,root,dados=self.criar(Path(d));limpar_arquivos(m,False)
            self.assertFalse((root/'versoes/v1/myBotWinthor.exe').exists())
            self.assertTrue((dados/'dados_bot.json').exists())

    def test_remocao_total_apaga_segredos_e_preserva_arquivos_desconhecidos(self):
        with tempfile.TemporaryDirectory() as d:
            m,root,dados=self.criar(Path(d));limpar_arquivos(m,True)
            self.assertFalse((dados/'dados_bot.json').exists())
            self.assertFalse((dados/'config_oracle.json').exists())
            self.assertTrue((dados/'anotacao.txt').exists())

    def test_inventario_externo_e_rejeitado_antes_de_apagar(self):
        with tempfile.TemporaryDirectory() as d:
            m,root,dados=self.criar(Path(d));info=json.loads(m.read_text())
            info['owned_files'].append('../dados/config_oracle.json');m.write_text(json.dumps(info))
            with self.assertRaises(ValueError):limpar_arquivos(m,True)
            self.assertTrue((dados/'dados_bot.json').exists())
            self.assertTrue((root/'versoes/v1/myBotWinthor.exe').exists())

    def test_marcador_incorreto_rejeitado(self):
        with tempfile.TemporaryDirectory() as d:
            m,root,dados=self.criar(Path(d));info=json.loads(m.read_text());info['product']='outra';m.write_text(json.dumps(info))
            with self.assertRaises(ValueError):plano(m,True)

    def test_inicio_usa_mesma_chave_apos_atualizacao(self):
        self.assertEqual(chave_inicio('C:/Apps/myBot/versoes/v1/myBotWinthor.exe'),chave_inicio('C:/Apps/myBot/versoes/v2/myBotWinthor.exe'))

    def test_remocao_total_limpa_temporarios_que_podem_conter_senhas(self):
        with tempfile.TemporaryDirectory() as d:
            m,root,dados=self.criar(Path(d));arquivo=dados/'.config_oracle.json.abc.tmp';arquivo.write_text('segredo ficticio')
            limpar_arquivos(m,True);self.assertFalse(arquivo.exists())

    def test_autostart_citado_e_persistido_sem_tocar_registry_real(self):
        from unittest.mock import patch,MagicMock
        from desktop.windows import inicializacao
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'Pasta com espacos';v=root/'versoes'/'v1';v.mkdir(parents=True);exe=v/'myBotWinthor.exe'
            (v/'desktop.json').write_text('{"autostart":false}')
            (root/'instalacao.json').write_text('{"autostart":false}')
            with patch('winreg.CreateKey',return_value=MagicMock()),patch('winreg.SetValueEx') as salvar:
                inicializacao(exe,True)
            self.assertIn('--autostart',salvar.call_args.args[-1])
            self.assertTrue(salvar.call_args.args[-1].startswith('"'))
            self.assertTrue(json.loads((v/'desktop.json').read_text())['autostart'])
            self.assertTrue(json.loads((root/'instalacao.json').read_text())['autostart'])
            with patch('winreg.CreateKey',return_value=MagicMock()),patch('winreg.DeleteValue') as remover:
                inicializacao(exe,False)
            remover.assert_called_once()
            self.assertFalse(json.loads((v/'desktop.json').read_text())['autostart'])

    def test_registro_identifica_usuario_sem_gravar_no_windows_real(self):
        from unittest.mock import patch,MagicMock
        from desktop.windows import registrar
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch('desktop.windows.inicializacao'),patch('winreg.CreateKey',return_value=MagicMock()),patch('winreg.SetValueEx') as escrever:
                sid=registrar(root,root/'versoes/v1/myBotWinthor.exe',root/'dados',False)
            self.assertTrue(sid.startswith('S-'))
            self.assertGreater(escrever.call_count,0)
