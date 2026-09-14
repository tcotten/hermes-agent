import contextlib
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('community_gateway', Path(__file__).resolve().parents[2] / 'scripts/hermes_community_gateway.py')
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class GatewayTests(unittest.TestCase):
    def test_missing_owner_does_not_fetch_secret(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(gateway, 'load_token') as load:
            self.assertEqual(gateway.main(), 1)
            load.assert_not_called()

    def test_fetch_error_never_discloses_token(self):
        secret = '123:SECRET_VALUE'
        output = io.StringIO()
        with patch.dict(os.environ, {'TELEGRAM_ALLOWED_USERS': '123'}), \
             patch.object(gateway, 'load_token', side_effect=RuntimeError(secret)), \
             contextlib.redirect_stderr(output):
            self.assertEqual(gateway.main(), 1)
        self.assertNotIn(secret, output.getvalue())

    def test_wrong_bot_never_starts_gateway(self):
        with patch.dict(os.environ, {'TELEGRAM_ALLOWED_USERS': '123'}), \
             patch.object(gateway, 'load_token', return_value='123:SECRET'), \
             patch.object(gateway.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"ok":true,"result":{"username":"different_bot"}}')), \
             patch.object(gateway.os, 'execvpe') as execute:
            self.assertEqual(gateway.main(), 1)
            execute.assert_not_called()

    def test_verified_token_goes_only_to_child_environment(self):
        # Telegram requires bot usernames to end in "bot" (BotFather enforces
        # this at creation), so the real registered username is
        # "GatherMinderBot", not the bare "GatherMinder" this test used to
        # assert against — that value could never occur for a real bot.
        with patch.dict(os.environ, {'TELEGRAM_ALLOWED_USERS': '123'}, clear=True), \
             patch.object(gateway, 'load_token', return_value='123:SECRET'), \
             patch.object(gateway.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"ok":true,"result":{"username":"GatherMinderBot"}}')), \
             patch.object(gateway.os, 'execvpe') as execute:
            gateway.main()
            command, argv, env = execute.call_args.args
            self.assertEqual(argv, ['hermes', 'gateway', 'run'])
            self.assertEqual(env['TELEGRAM_BOT_TOKEN'], '123:SECRET')
            self.assertEqual(env['TELEGRAM_GROUP_ALLOWED_USERS'], '123')
            self.assertEqual(env['TELEGRAM_ALLOW_ALL_USERS'], 'false')
            self.assertNotIn('TELEGRAM_BOT_TOKEN', os.environ)


if __name__ == '__main__':
    unittest.main()
