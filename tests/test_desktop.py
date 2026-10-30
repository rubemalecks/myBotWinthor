import unittest, tempfile, json, zipfile
from pathlib import Path
from unittest.mock import patch
from desktop.common import validar_dados
from desktop.installer import instalar, extrair_seguro

class DesktopTests(unittest.TestCase):
    def test_atualizacao_preserva_dados_e_versao_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta); dados=root/'dados';dados.mkdir();arquivo=dados/'dados_bot.json'
            original=b'{"usuarios":{"123":{"nome":"Pessoa"}}}';arquivo.write_bytes(original)
            pacote=root/'payload.zip'
            with zipfile.ZipFile(pacote,'w') as z:z.writestr('myBotWinthor.exe',b'teste')
            with patch('desktop.installer.subprocess.run') as executar, patch('ctypes.windll.shell32.SHGetFolderPathW',return_value=1):
                executar.return_value.returncode=0
                with patch('desktop.installer.subprocess.CREATE_NO_WINDOW',0,create=True):
                    exe,_=instalar(root/'programa',dados,pacote)
                    outro,_=instalar(root/'programa',dados,pacote)
            self.assertTrue(exe.exists());self.assertTrue(outro.exists());self.assertNotEqual(exe,outro)
            self.assertEqual(arquivo.read_bytes(),original)
            self.assertEqual(json.loads((outro.parent/'desktop.json').read_text())['data_dir'],str(dados.resolve()))

    def test_zip_traversal_bloqueado(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);pacote=root/'pacote.zip'
            with zipfile.ZipFile(pacote,'w') as z:z.writestr('../escape.exe',b'x')
            with self.assertRaises(ValueError):extrair_seguro(pacote,root/'destino')
            self.assertFalse((root/'escape.exe').exists())

    def test_json_invalido_nao_e_substituido(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'dados_bot.json';arquivo.write_text('{quebrado')
            with self.assertRaises(ValueError):validar_dados(pasta)
            self.assertEqual(arquivo.read_text(),'{quebrado')

    def test_distribuicao_contem_exes_guia_e_hashes(self):
        import hashlib
        from desktop.build_windows import organizar_distribuicao
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta); runtime=root/'runtime';runtime.mkdir()
            (runtime/'myBotWinthor.exe').write_bytes(b'gerenciador')
            (runtime/'_internal').mkdir();(runtime/'_internal'/'python.dll').write_bytes(b'dll')
            pacote=root/'payload.zip'
            from desktop.build_windows import compactar
            compactar(runtime,pacote)
            setup=root/'setup.exe';setup.write_bytes(b'instalador')
            saida=root/'distribuicao';organizar_distribuicao(saida,runtime,pacote,setup)
            self.assertEqual((saida/'cliente'/'Instalar-myBotWinthor.exe').read_bytes(),b'instalador')
            self.assertTrue((saida/'portatil'/'_internal'/'python.dll').is_file())
            self.assertTrue((saida/'LEIA-ME.txt').is_file())
            for linha in (saida/'SHA256.txt').read_text(encoding='utf-8').splitlines():
                digest,nome=linha.split('  ',1)
                self.assertEqual(hashlib.sha256((saida/nome).read_bytes()).hexdigest(),digest)

    def test_build_novo_remove_residuos_sem_apagar_distribuicao_anterior(self):
        from desktop.build_windows import organizar_distribuicao, compactar
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);runtime=root/'runtime';(runtime/'_internal').mkdir(parents=True)
            (runtime/'myBotWinthor.exe').write_bytes(b'exe')
            setup=root/'setup.exe';setup.write_bytes(b'setup')
            payload=root/'payload.zip';compactar(runtime,payload)
            saida=root/'distribuicao';saida.mkdir();(saida/'residuo.txt').write_text('anterior')
            organizar_distribuicao(saida,runtime,payload,setup)
            self.assertFalse((saida/'residuo.txt').exists())
            backups=list((root/'.build/distribuicao').glob('anterior-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual((backups[0]/'residuo.txt').read_text(),'anterior')
            with zipfile.ZipFile(saida/'myBotWinthor-cliente.zip') as z:
                self.assertIn('Instalar-myBotWinthor.exe',z.namelist())
                self.assertIn('LEIA-ME.txt',z.namelist())
                self.assertIn('SHA256.txt',z.namelist())

    def test_falha_ao_preparar_preserva_distribuicao(self):
        from desktop.build_windows import organizar_distribuicao, compactar
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);runtime=root/'runtime';(runtime/'_internal').mkdir(parents=True)
            (runtime/'myBotWinthor.exe').write_bytes(b'exe')
            payload=root/'payload.zip';compactar(runtime,payload)
            setup=root/'setup.exe';setup.write_bytes(b'setup')
            saida=root/'saida';saida.mkdir();(saida/'anterior').write_text('manter')
            with patch('desktop.build_windows.shutil.copytree',side_effect=OSError('falhou')):
                with self.assertRaises(OSError):organizar_distribuicao(saida,runtime,payload,setup)
            self.assertEqual((saida/'anterior').read_text(),'manter')

    def test_empacotamento_rejeita_segredos_e_payload_desatualizado(self):
        from desktop.build_windows import compactar, organizar_distribuicao
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);runtime=root/'runtime';(runtime/'_internal').mkdir(parents=True)
            (runtime/'myBotWinthor.exe').write_bytes(b'v1')
            payload=root/'payload.zip';compactar(runtime,payload)
            (runtime/'myBotWinthor.exe').write_bytes(b'v2')
            with self.assertRaises(ValueError):organizar_distribuicao(root/'saida',runtime,payload,root/'setup.exe')
            for nome in ('.env', '.env.producao','campos_produto.json','desktop.json','app.log'):
                arquivo=runtime/nome;arquivo.write_text('privado')
                with self.assertRaises(ValueError):compactar(runtime,root/'bloqueado.zip')
                arquivo.unlink()

    def test_publicacao_com_falha_restaura_a_distribuicao_anterior(self):
        from desktop.build_windows import organizar_distribuicao, compactar
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);runtime=root/'runtime';(runtime/'_internal').mkdir(parents=True)
            (runtime/'myBotWinthor.exe').write_bytes(b'exe')
            payload=root/'payload.zip';compactar(runtime,payload)
            setup=root/'setup.exe';setup.write_bytes(b'setup')
            saida=root/'saida';saida.mkdir();(saida/'anterior').write_text('manter')
            original=Path.rename
            def renomear(caminho,destino):
                if caminho.name.startswith('stage-'):
                    raise OSError('Falha de publicação simulada')
                return original(caminho,destino)
            with patch.object(Path,'rename',renomear):
                with self.assertRaises(OSError):organizar_distribuicao(saida,runtime,payload,setup)
            self.assertEqual((saida/'anterior').read_text(),'manter')

    def test_publicacao_nao_pode_substituir_pastas_do_codigo(self):
        from desktop.build_windows import organizar_distribuicao
        projeto=Path(__file__).resolve().parents[1]
        for nome in ('docs','modulos','desktop','.git','tests'):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                organizar_distribuicao(projeto/nome,projeto/'runtime-inexistente',projeto/'payload-inexistente',projeto/'exe-inexistente')
