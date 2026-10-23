import sqlite3
import unittest
from modulos.regras_margem import normalizar_regra, CompiladorSQL


class RegrasMargemTests(unittest.TestCase):
    def calcular(self, ajustes):
        regra = normalizar_regra({'nome': 'Teste', 'produtos': [6], 'ajustes': ajustes})
        compilador = CompiladorSQL()
        sql = compilador.ajustes(regra)['percentual']
        parametros = {k: float(v) for k, v in compilador.parametros.items()}
        with sqlite3.connect(':memory:') as banco:
            return banco.execute(f'SELECT {sql} FROM (SELECT 20.0 PVENDA) T CROSS JOIN (SELECT 10.0 CUSTOULTENT) E', parametros).fetchone()[0]

    def test_valor_fixo_no_custo_antes_da_formula(self):
        self.assertAlmostEqual(self.calcular([{'alvo':'custo','operacao':'+','tipo':'valor','valor':'2,5'}]), 60)

    def test_percentual_relativo_diferente_de_pontos(self):
        self.assertAlmostEqual(self.calcular([{'alvo':'resultado','operacao':'-','tipo':'percentual','valor':'10'}]), 90)
        self.assertAlmostEqual(self.calcular([{'alvo':'resultado','operacao':'+','tipo':'valor','valor':'5'}]), 105)

    def test_custo_invalido_nao_divide_por_zero(self):
        self.assertIsNone(self.calcular([{'alvo':'custo','operacao':'-','tipo':'valor','valor':'10'}]))

    def test_where_compila_com_valores_em_binds(self):
        regra = normalizar_regra({'nome':'Filtro','where':"PCPRODUT.CODEPTO = 108 AND PCEST.CODFILIAL IN (1, 2)"})
        compiler = CompiladorSQL()
        sql = compiler.condicao(regra)
        self.assertIn('P.CODEPTO', sql)
        self.assertNotIn('108', sql)
        self.assertEqual(len(compiler.parametros), 3)

    def test_where_rejeita_comandos_e_funcoes(self):
        for filtro in ('1=1; DELETE FROM PCPRODUT', 'PCPRODUT.CODPROD IN (SELECT CODPROD FROM PCPRODUT)', '__import__(1)', 'OUTRA.CAMPO=1'):
            with self.subTest(filtro=filtro), self.assertRaises(ValueError):
                normalizar_regra({'nome':'Inválida','where':filtro})

    def test_salvar_exige_escopo_mas_previa_nao(self):
        with self.assertRaises(ValueError):
            normalizar_regra({'nome':'Sem filtro'})
        normalizar_regra({'nome':'Simular'}, salvar=False)
