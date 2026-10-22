import asyncio
import json
import unittest
from types import SimpleNamespace

from modulos import bot


class LogsConsultasTests(unittest.TestCase):
    def setUp(self):
        self.update = SimpleNamespace(update_id=42, effective_user=SimpleNamespace(
            id=123, full_name='Pessoa\nTeste', username='pessoa'))

    def test_registra_usuario_busca_resultado_e_tempo(self):
        with self.assertLogs(bot.logger, level='INFO') as logs:
            resultado = asyncio.run(bot.consultar_com_log(
                self.update, 'produto', lambda: [{'codprod': 6}], codigo='6'))
        self.assertEqual(len(resultado), 1)
        inicio, fim = [json.loads(record.getMessage().removeprefix('CONSULTA ')) for record in logs.records]
        self.assertEqual(inicio['usuario_id'], 123)
        self.assertEqual(inicio['codigo'], '6')
        self.assertEqual(inicio['etapa'], 'INICIO')
        self.assertEqual(fim['etapa'], 'CONCLUIDO')
        self.assertEqual(fim['registros'], 1)
        self.assertGreaterEqual(fim['duracao_ms'], 0)
        self.assertNotIn('\n', logs.records[0].getMessage())

    def test_erro_registra_codigo_sem_mensagem_sensivel(self):
        def falhar():
            raise RuntimeError('ORA-00942 segredo-nao-registrar')
        with self.assertLogs(bot.logger, level='INFO') as logs:
            with self.assertRaises(RuntimeError):
                asyncio.run(bot.consultar_com_log(self.update, 'produto', falhar))
        erro = json.loads(logs.records[-1].getMessage().removeprefix('CONSULTA '))
        self.assertEqual(erro['etapa'], 'ERRO')
        self.assertEqual(erro['codigos'], ['ORA-00942'])
        self.assertNotIn('segredo-nao-registrar', '\n'.join(logs.output))
