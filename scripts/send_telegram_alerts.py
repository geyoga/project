"""Send crawler alert output to Telegram when credentials are configured."""

import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    text = sys.stdin.read().strip()
    if not text or text == "NO_ALERTS":
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID", file=sys.stderr)
        return 0

    while text:
        chunk = text[:4096]
        if len(text) > 4096 and "\n" in chunk:
            chunk = chunk[:chunk.rfind("\n") + 1]
        text = text[len(chunk):]
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": "true",
        }).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"Telegram returned HTTP {response.status}")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Telegram returned HTTP {error.code}") from None
    return 0


if __name__ == "__main__":
    sys.exit(main())
