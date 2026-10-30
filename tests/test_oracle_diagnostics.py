import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from desktop.diagnostics import diagnosticar_oracle,validar_criptografia

class OracleDiagnosticsTests(unittest.TestCase):
    def config(self,pasta):
        p=Path(pasta)/'oracle.json';p.write_text(json.dumps({'ORACLE_USER':'usuario-ficticio','ORACLE_PASSWORD':'segredo-ficticio','ORACLE_HOST':'host-ficticio','ORACLE_PORT':'1521','ORACLE_SERVICE':'servico-ficticio','ORACLE_CLIENT_DIR':''}));return p

    def test_primitivas_da_autenticacao_estao_disponiveis(self):
        self.assertTrue(validar_criptografia())

    def test_teste_so_consulta_dual_e_retorna_resultado_sem_segredos(self):
        with tempfile.TemporaryDirectory() as d,patch('oracledb.connect') as conectar:
            cursor=conectar.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value=(1,)
            resultado=diagnosticar_oracle(self.config(d))
            self.assertTrue(resultado['ok'])
            self.assertEqual([c.args[0] for c in cursor.execute.call_args_list],['SET TRANSACTION READ ONLY','SELECT 1 FROM DUAL'])
            self.assertNotIn('segredo-ficticio',str(resultado))

    def test_erros_revelam_so_codigo_e_classe(self):
        import oracledb
        with tempfile.TemporaryDirectory() as d,patch('oracledb.connect',side_effect=oracledb.NotSupportedError('DPY-3016 segredo-ficticio')):
            resultado=diagnosticar_oracle(self.config(d))
            self.assertFalse(resultado['ok']);self.assertEqual(resultado['codigos'],['DPY-3016'])
            self.assertNotIn('segredo-ficticio',str(resultado))
