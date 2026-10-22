import asyncio
import threading
import unittest
from unittest.mock import patch

from modulos import bot


class InicializacaoBotTests(unittest.TestCase):
    def test_polling_tem_loop_proprio_na_thread(self):
        loops = []
        with patch.object(bot, 'ApplicationBuilder') as builder:
            app = builder.return_value.token.return_value.build.return_value
            app.run_polling.side_effect = lambda **kwargs: loops.append(asyncio.get_event_loop())
            thread = threading.Thread(target=bot.executar_bot_telegram, args=('token-ficticio',))
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(loops), 1)
            self.assertTrue(loops[0].is_closed())
            app.run_polling.assert_called_once_with(stop_signals=None)
            app.add_error_handler.assert_called_once_with(bot.erro_telegram)
