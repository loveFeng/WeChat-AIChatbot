# -*- coding: utf-8 -*-
import json
import os
import pickle
import time
import datetime

from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
import config as RobotConfig
from channel import channel_factory
import plugins
from plugins import *
from common.log import logger


@plugins.register(name="SystemInfo", desire_priority=998, hidden=True,
                  desc="A simple plugin handles system information", version="0.1", author="Joe")
class SystemInfo(Plugin):
    def __init__(self):
        super().__init__()
        self.datas = None
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

        self.group_welcome = gconf.get("group_welcome", "")
        self.single_welcome = gconf.get("single_welcome", "")
        self.vip_welcome = gconf.get("vip_welcome", "")
        self.vip_check = gconf.get("vip_check", False)
        self.interval = gconf.get("chat_interval", 180)
        self.free_day_count = gconf.get("free_day_count", 2)
        self.admin_auto_prefix = gconf.get("admin_auto_prefix", False)

        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_handle_check
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_admin_error
        self.load_data()
        Godcmd = pconf("Godcmd")
        self.admin_users = Godcmd["admin_users"]  # 管理员账号
        logger.info("[SystemInfo] inited")

    def handle_check_vip(self, e_context):
        """
        判断是否vip，vip超时问题
        房间是vip的，所有人都不计算时间间隔
        之后再判断个人是否为vip
        私聊限定次数后，必须管理员打开vip
        """
        if not self.vip_check:
            logger.debug("[SystemInfo] not check vip")
            return

        msg: ChatMessage = e_context['context']['msg']
        reply = Reply()
        reply.type = ReplyType.INFO

        if msg.is_group:
            room = conf().get_user_data(msg.from_user_id)
            logger.debug("[vip] room:{}".format(room))
            if not room.get("vip", False):
                wxid = msg.actual_user_id
                userdata = conf().get_user_data(wxid)
                logger.debug("[vip] user:{}".format(userdata))
                if not userdata.get("vip", False):
                    interval = int(time.time() - userdata["last_time"])
                    logger.debug("[vip] interval:{}".format(interval))
                    if interval < self.interval:
                        reply.content = (
                            "@{} 群用户提问间隔{}秒，还需等待{}秒,欢迎加我好友私聊".format(userdata[msg.from_user_id],
                                                                                          self.interval,
                                                                                          (self.interval - interval)))
                        e_context['reply'] = reply
                        e_context.action = EventAction.BREAK_PASS
                    else:
                        userdata["last_time"] = time.time()

        else:
            wxid = msg.from_user_id
            userdata = conf().get_user_data(wxid)
            logger.debug("[vip] user:{}".format(userdata))
            if self.datas.get(wxid) is None:
                self.datas[wxid] = {}

            now = datetime.datetime.now()
            day_key = "{}-{}-{}".format(now.year, now.month, now.day)

            if self.datas[wxid].get(day_key) is None:
                self.datas[wxid] = {day_key: 0}

            if self.datas[wxid][day_key] > self.free_day_count:
                if not (userdata.get("vip", False) and userdata.get("vip_time", time.time() - 1) > time.time()):
                    reply.content = "今日询问次数已用完，请明天再问！或者支持一下！{}".format(self.vip_welcome)
                    e_context['reply'] = reply
                    e_context.action = EventAction.BREAK_PASS
            else:
                self.datas[wxid][day_key] += 1
                self.save_datas()

    def handle_system(self, e_context):
        """
        处理系统消息和红包。目前是入群消息和好友第一次通过消息
        """
        reply = Reply()
        reply.type = ReplyType.INFO
        content = e_context['context'].content
        if content.endswith("加入了群聊"):
            nick = content.split('"邀请"')[1].split('"')[0]
            reply.content = "欢迎 {} 入群！{}".format(nick, self.group_welcome)
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
        elif content.endswith("分享的二维码加入群聊"):
            nick = content.split('"')[1]
            reply.content = "欢迎 {} 入群！{}".format(nick, self.group_welcome)
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
        elif content.endswith("现在可以开始聊天了。"):
            reply.content = self.single_welcome
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
        elif content.startswith("收到红包"):
            msg: ChatMessage = e_context['context']['msg']
            if not msg.is_group:
                reply.content = "收到{}({})红包".format(msg.from_user_nickname, msg.from_user_id)
                e_context['reply'] = reply
                receiver = e_context['context']['receiver']
                logger.debug("[SystemInfo] 收到红包 receiver=" + receiver)
                e_context['context']['receiver'] = self.admin_users
                e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
            else:
                logger.debug("[SystemInfo]群 {}（{}）收到红包".format(msg.from_user_nickname, msg.from_user_id))
                reply.content = "\"{}\"群里有红包".format(msg.from_user_nickname)
                e_context['reply'] = reply
                e_context['context']['receiver'] = self.admin_users
                e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑

    def on_handle_context(self, e_context: EventContext):
        logger.debug(f"[SystemInfo] on_handle_context. type={e_context['context']}")
        # if e_context['context'].type == ContextType.OTHER:
        #     self.handle_system(e_context)
        # elif e_context['context'].type == ContextType.TEXT:
        #     self.handle_check_vip(e_context)
        e_context.action = EventAction.CONTINUE

    def on_handle_check(self, e_context: EventContext):
        """
        检查用户是否被禁用
        判断单聊时是否为管理员用户，如果是自动添加上前缀
        todo 允许AI接管的用户
        """

        # msg: ChatMessage = e_context['context']['msg']
        # userdata = conf().get_user_data(msg.from_user_id)
        # if userdata.get("stop", False) and msg.from_user_id != self.admin_users:
        #     e_context.action = EventAction.BREAK_PASS

        logger.debug(
            "[SystemInfo] on_handle_check isgroup:{},context:{}".format(e_context['context'].get("isgroup", False),
                                                                        e_context['context']))
        if self.admin_auto_prefix:
            if not e_context['context'].get("isgroup", False):
                user = e_context["context"]["receiver"]
                # logger.debug("[SystemInfo] on_handle_check user:{},admin_users:{},type:{},content-type:{}".format(user,
                # self.admin_users , e_context['context'].type, type(e_context["context"]["content"])))
                if user in self.admin_users and ContextType.TEXT == e_context['context'].type:
                    content = e_context["context"]["content"]
                    match_prefix = self.check_prefix(content, conf().get("single_chat_prefix", [""]))
                    # logger.debug("[SystemInfo] on_handle_check content:{},match_prefix:{}".format(content, match_prefix))
                    if not match_prefix:
                        e_context["context"]["content"] = conf().get("single_chat_prefix", [""])[0] + content
                        # logger.debug("[SystemInfo] change on_handle_check type{},".format(e_context['context']))

    def on_send_admin_error(self, e_context: EventContext):
        """
        检查错误消息发送给管理员
        """
        reply = e_context['reply']
        if reply.type == ReplyType.ERROR:
            logger.debug("[SystemInfo] on_send_admin_error type{},".format(reply))
            msg: ChatMessage = e_context['context']['msg']
            channel_name = RobotConfig.conf().get("channel_type", "wx")
            channel = channel_factory.create_channel(channel_name)
            # channel.send(reply, context)
            # WXChannel().admin_broad_msg("s", "出错消息 msg={},reply={}".format(msg.content, reply.content),
            #                             json.dumps([self.admin_users]))

    def get_help_text(self, **kwargs):
        help_text = "处理系统消息,检查vip"
        return help_text

    def load_data(self):
        config_path = os.path.join(self.file_dir, 'datas.pkl')
        try:
            with open(config_path, 'rb') as f:
                self.datas = pickle.load(f)
                logger.info("[SystemInfo]datas loaded.")
        except Exception as e:
            logger.info("[SystemInfo]datas error: {}".format(e))
            self.datas = {}

    def save_datas(self):
        config_path = os.path.join(self.file_dir, 'datas.pkl')
        try:
            with open(config_path, 'wb') as f:
                pickle.dump(self.datas, f)
                logger.info("[SystemInfo]datas saved.")
        except Exception as e:
            logger.info("[SystemInfo]datas error: {}".format(e))

    def read_file(self, path):
        with open(path, mode='r', encoding='utf-8') as f:
            return f.read()

    def check_prefix(self, content, prefix_list):
        if not prefix_list:
            return None
        for prefix in prefix_list:
            if content.startswith(prefix):
                return prefix
        return None
