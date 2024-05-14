import logging
import os
import time

from common import log

os.environ['ntchat_LOG'] = "DEBUG"

import ntchat

wechatnt = ntchat.WeChat()

log1 = logging.getLogger("WeChatInstance")
log.reset_logger(log1, "WeChatInstance")

log2 = logging.getLogger("WeChatManager")
log.reset_logger(log2, "WeChatManager")

def forever():
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        ntchat.exit_()
        os._exit(0)
        # sys.exit(0)
