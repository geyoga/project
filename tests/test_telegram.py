import io
import unittest
from unittest import mock

from scripts import send_telegram_alerts


class TelegramTests(unittest.TestCase):
    def test_no_alerts_never_calls_telegram(self):
        with mock.patch.object(send_telegram_alerts.sys, "stdin", io.StringIO("NO_ALERTS")):
            with mock.patch.object(send_telegram_alerts.urllib.request, "urlopen") as send:
                self.assertEqual(send_telegram_alerts.main(), 0)
                send.assert_not_called()

    def test_long_alerts_are_split_before_sending(self):
        with mock.patch.dict(send_telegram_alerts.os.environ, {
            "TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "123",
        }):
            with mock.patch.object(send_telegram_alerts.sys, "stdin", io.StringIO("hello\n" * 750)):
                with mock.patch.object(send_telegram_alerts.urllib.request, "urlopen") as send:
                    send.return_value.__enter__.return_value.status = 200
                    self.assertEqual(send_telegram_alerts.main(), 0)
                    self.assertEqual(send.call_count, 2)
                    self.assertTrue(all(len(call.args[0].data) < 10000 for call in send.call_args_list))


if __name__ == "__main__":
    unittest.main()
