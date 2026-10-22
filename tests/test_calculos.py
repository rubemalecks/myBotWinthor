import unittest
from decimal import Decimal

from modulos.calculos import ganho_sobre_custo


class GanhoSobreCustoTests(unittest.TestCase):
    def test_percentual_usa_custo_como_base(self):
        self.assertEqual(ganho_sobre_custo(100, 50), Decimal('100'))
        self.assertEqual(ganho_sobre_custo(100, 100), Decimal('0'))
        self.assertEqual(ganho_sobre_custo(50, 100), Decimal('-50'))

    def test_valores_do_departamento(self):
        self.assertEqual(round(ganho_sobre_custo('20184.27', '11643.20'), 2), Decimal('73.36'))

    def test_custo_invalido_nao_divide_por_zero(self):
        for preco, custo in ((10, 0), (10, -1), (10, None), (None, 10), (0, 10)):
            with self.subTest(preco=preco, custo=custo):
                self.assertIsNone(ganho_sobre_custo(preco, custo))
