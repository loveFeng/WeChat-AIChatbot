import plugins
import threading

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel import channel_factory
from common.log import logger
from plugins import *
import config as RobotConfig


@plugins.register(
    name="timeout",
    desire_priority=997,
    hidden=True,
    desc="A plugin to check msg reply time out",
    version="0.1",
    author="Joe",
)
class Timeout(Plugin):
    def __init__(self):
        super().__init__()
        self.timer = None  # 定时器
        self.user_id = None  # 当前微信的用户id
        curdir = os.path.dirname(__file__)
        self.file_dir = curdir
        config_path = os.path.join(curdir, "config.json")
        gconf = super().load_config()
        if not gconf:
            if not os.path.exists(config_path):
                config_str = self.read_file(os.path.join(curdir, "config.json.template"))
                gconf = json.loads(config_str)
                with open(config_path, "w") as f:
                    json.dump(gconf, f, indent=4)
            else:
                with open(config_path, "r") as f:
                    gconf = json.load(f)

        self.msg_check = gconf.get("check", False)
        self.msg_check_time = gconf.get("out_time", 120)
        self.admin_users = gconf.get("admins", [])
        Godcmd = pconf("Godcmd")
        self.admin_users.extend(Godcmd["admin_users"])  # 管理员账号

        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_handle_check

        logger.info(f"[Timeout] inited, check:{self.msg_check}, time:{self.msg_check_time}, admins:{self.admin_users}")

    def send_msg(self):
        channel_name = RobotConfig.conf().get("channel_type", "wx")
        channel = channel_factory.create_channel(channel_name)

        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = "[timeout]有未处理的个人消息，请及时处理！"
        context = Context(ContextType.TEXT)
        logger.debug(f"[Timeout] send_msg, user:{self.admin_users}, reply:{reply}, context:{context}")
        for user in self.admin_users:
            context["receiver"] = user
            channel.send(reply, context)

    def on_handle_check(self, e_context: EventContext):
        if self.msg_check and not e_context['context'].get("isgroup", False) and e_context['context'].type.value < ContextType.SHARING.value:
            user = e_context["context"]["receiver"]
            cmsg = e_context["context"]["msg"]
            if self.user_id is None:
                channel_name = RobotConfig.conf().get("channel_type", "wx")
                channel = channel_factory.create_channel(channel_name)
                self.user_id = channel.user_id

            if cmsg.from_user_id == self.user_id:
                if self.timer is not None and self.timer.is_alive():
                    self.timer.cancel()
                    logger.debug(f"[Timeout] cancel timer, user:{user}, msg:{cmsg}")
            elif user not in self.admin_users:
                if self.timer is None or not self.timer.is_alive():
                    self.timer = threading.Timer(self.msg_check_time, self.send_msg)
                    self.timer.start()
                    logger.debug(f"[Timeout] start timer, user:{user}, msg:{cmsg}")

    def get_help_text(self, verbose=False, **kwargs):
        short_help_text = " 检测是否处理消息，未处理发给管理员。"

        if not verbose:
            return short_help_text

        help_text = "检测消息处理！\n"
        help_text += " 当消息超时未处理，发送消息给管理员\n"
        return help_text

    def read_file(self, path):
        with open(path, mode='r', encoding='utf-8') as f:
            return f.read()
