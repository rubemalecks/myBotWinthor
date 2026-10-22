import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import database


class ConsultaProdutoTests(unittest.TestCase):
    def test_sonda_valida_consulta_mesmo_com_tabela_vazia(self):
        with patch('database.conectar') as conectar:
            cursor = conectar.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            self.assertTrue(database.testar_conexao_oracle())
            sql, params = cursor.execute.call_args.args
            self.assertIn('WHERE 1=0 AND (', sql)
            self.assertIn('PCTABPR', sql)
            self.assertEqual(params['CODPROD'], 0)

    def test_sonda_nao_confunde_login_com_acesso_as_tabelas(self):
        with patch('database.conectar') as conectar:
            cursor = conectar.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            cursor.execute.side_effect = [None, database.oracledb.DatabaseError(MagicMock(code=942))]
            with self.assertRaises(database.ErroAcessoWinthor):
                database.testar_conexao_oracle()

    def test_cliente_distribuido_e_detectado_automaticamente(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta).resolve()
            (raiz / "oracle_client").mkdir()
            with patch.object(database, "BASE_DIR", raiz), patch.object(database, "_oracle_client_inicializado", False), patch("database.oracledb.init_oracle_client") as iniciar:
                database._inicializar_oracle_client({"ORACLE_CLIENT_DIR": ""})
                database._inicializar_oracle_client({"ORACLE_CLIENT_DIR": ""})
                iniciar.assert_called_once_with(lib_dir=str(raiz / "oracle_client"))

    def test_caminho_relativo_usa_pasta_da_api(self):
        with patch.object(database, "_oracle_client_inicializado", False), patch("database.oracledb.init_oracle_client") as iniciar:
            database._inicializar_oracle_client({"ORACLE_CLIENT_DIR": "oracle_client"})
            iniciar.assert_called_once_with(lib_dir=str((database.BASE_DIR / "oracle_client").resolve()))

    @patch("database.executar_consulta", return_value=[])
    def test_consulta_por_codauxiliar2(self, executar):
        database.consultar_produto("12345678", ("codauxiliar2",))

        sql, parametros = executar.call_args.args
        self.assertIn("P.CODAUXILIAR2 = :CODAUXILIAR2", sql)
        self.assertEqual(parametros, {"CODAUXILIAR2": 12345678})

    def test_rejeita_campos_de_busca_desconhecidos(self):
        with self.assertRaises(ValueError):
            database.consultar_produto("123", ("campo_injetado",))


if __name__ == "__main__":
    unittest.main()
