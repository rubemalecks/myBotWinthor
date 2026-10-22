import unittest

from modulos.margem_departamento import formatar_relatorio


class RelatorioMargemTests(unittest.TestCase):
    def setUp(self):
        self.departamento = {"codepto": 10, "descricao": "Mercearia"}
        self.linhas = [{
            "numregiao": 1,
            "nome_tabela": "Varejo",
            "total_precos": 100,
            "total_custos": 70,
            "produtos_validos": 2,
            "total_produtos": 3,
            "sem_preco": 1,
            "sem_custo": 0,
            "custo_zero": 0,
        }]

    def test_perfil_de_margem_nao_exibe_valores_de_custo(self):
        texto = formatar_relatorio(
            self.departamento, 1, self.linhas, incluir_custos=False
        )

        self.assertIn("Lucro presumido sobre o custo: 42,86%", texto)
        self.assertNotIn("Soma dos custos", texto)
        self.assertNotIn("Diferença bruta", texto)
        self.assertNotIn("Sem custo", texto)

    def test_perfil_de_custos_mantem_detalhamento(self):
        texto = formatar_relatorio(
            self.departamento, 1, self.linhas, incluir_custos=True
        )

        self.assertIn("Soma dos custos", texto)
        self.assertIn("Diferença bruta", texto)


if __name__ == "__main__":
    unittest.main()
