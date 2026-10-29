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


class CampoBaseCustoTests(unittest.TestCase):
    def regra(self, **extras):
        return normalizar_regra({'nome': 'Custo real', 'todos_produtos': True,
                                 'campo_custo': 'PCEST.CUSTOREAL', **extras})

    def test_calcula_sobre_coluna_escolhida_antes_dos_ajustes(self):
        from modulos.regras_margem import expressao_regra
        regra = self.regra(ajustes=[{'alvo': 'custo', 'operacao': '+', 'tipo': 'valor', 'valor': '2'}])
        compilador = CompiladorSQL()
        calculos = compilador.ajustes(regra)
        params = {k: float(v) for k, v in compilador.parametros.items()}
        with sqlite3.connect(':memory:') as banco:
            valores = banco.execute(f"SELECT {calculos['custo']}, {calculos['percentual']}, {calculos['base']} FROM (SELECT 30.0 PVENDA) T CROSS JOIN (SELECT 5.0 CUSTOULTENT, 18.0 CUSTOREAL) E", params).fetchone()
        self.assertEqual(valores, (20, 50, 20))
        self.assertIn('PCEST.CUSTOREAL', expressao_regra(regra))

    def test_base_zero_nula_ou_negativa_nao_produz_percentual(self):
        for valor in ('0', 'NULL', '-1'):
            c = CompiladorSQL().ajustes(self.regra())
            with sqlite3.connect(':memory:') as banco:
                resultado = banco.execute(f"SELECT {c['percentual']} FROM (SELECT 30.0 PVENDA) T CROSS JOIN (SELECT {valor} CUSTOREAL) E").fetchone()[0]
            self.assertIsNone(resultado)

    def test_validacao_restringe_tabela_metadados_e_tipo(self):
        from modulos.regras_margem import validar_catalogo
        for campo in ('PCNFENT.CUSTOREAL', 'PCTABPR.PVENDA', 'PCEST.X;DELETE', 'PCEST.CUSTOULTENT + 1'):
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                self.regra(campo_custo=campo)
        with self.assertRaises(ValueError):
            validar_catalogo(self.regra(), [])
        with self.assertRaises(ValueError):
            validar_catalogo(self.regra(), [{'campo': 'PCEST.CUSTOREAL', 'numerico': False}])
        validar_catalogo(self.regra(), [{'campo': 'PCEST.CUSTOREAL', 'numerico': True}])

    def test_regra_antiga_preserva_base_e_formato(self):
        regra = normalizar_regra({'nome': 'Antiga', 'todos_produtos': True})
        self.assertNotIn('campo_custo', regra)
        self.assertEqual(CompiladorSQL().ajustes(regra)['custo'], 'E.CUSTOULTENT')

    def test_consulta_produto_e_departamento_usam_nova_base(self):
        from unittest.mock import patch
        from modulos import database, margem_departamento
        regra = {'id': 'a' * 24, **self.regra()}
        with patch.object(database, 'executar_consulta', return_value=[]) as consulta:
            database.consultar_calculos_formulas_produto(6, regras=[regra], rascunho=regra)
        sql, binds = consulta.call_args.args
        self.assertIn('E.CUSTOREAL AS VALOR_0', sql)
        self.assertIn('E.CUSTOREAL', sql)
        self.assertIn('P.DTEXCLUSAO IS NULL', sql)
        self.assertEqual(binds['FM_CODPROD'], 6)
        with patch.object(margem_departamento, 'executar_consulta', return_value=[]) as consulta:
            margem_departamento._calcular_com_regras(1, 2, 3, None, [regra])
        self.assertIn('E.CUSTOREAL', consulta.call_args.args[0])
        self.assertIn('P.DTEXCLUSAO IS NULL', consulta.call_args.args[0])
