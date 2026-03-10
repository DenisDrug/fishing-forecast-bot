# -*- coding: utf-8 -*-
from pathlib import Path

path = Path('src/bot_handlers.py')
text = path.read_text(encoding='cp1251', errors='ignore')
start = text.index('        await update.message.reply_text(')
end = text.index('\n    def _get_time_period_offset', start)

new_block = '
        thinking_msg = await update.message.reply_text(
