import unittest
from unittest.mock import patch

from modulos.rede import enderecos_painel


class EnderecosPainelTests(unittest.TestCase):
    @patch('modulos.rede.detectar_ip_rede', return_value='192.168.0.16')
    def test_mostra_local_e_rede_com_porta_escolhida(self, detectar):
        self.assertEqual(enderecos_painel('9000'),
                         ('http://127.0.0.1:9000', 'http://192.168.0.16:9000'))

    def test_loopback_nao_anuncia_acesso_pela_rede(self):
        self.assertEqual(enderecos_painel('8765', '127.0.0.1'),
                         ('http://127.0.0.1:8765', None))

    @patch('modulos.rede.detectar_ip_rede', return_value=None)
    def test_sem_ip_nao_inventa_endereco(self, detectar):
        self.assertEqual(enderecos_painel('9000'), ('http://127.0.0.1:9000', None))
