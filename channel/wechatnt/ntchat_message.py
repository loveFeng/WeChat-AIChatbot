import datetime
import json
import os
import re
import time

from bridge.context import ContextType
from channel.chat_message import ChatMessage
from channel.wechatnt.nt_run import wechatnt
from channel.wechatnt.WechatImageDecoder import WechatImageDecoder
from common.log import logger
import ntchat


def ensure_file_ready(file_path, timeout=10, interval=0.5):
    """确保文件可读。

    :param file_path: 文件路径。
    :param timeout: 超时时间，单位为秒。
    :param interval: 检查间隔，单位为秒。
    :return: 文件是否可读。
    """
    start_time = time.time()
    while True:
        if os.path.exists(file_path) and os.access(file_path, os.R_OK):
            return True
        elif time.time() - start_time > timeout:
            return False
        else:
            time.sleep(interval)


def get_nickname(contacts, wxid):
    for contact in contacts:
        if contact['wxid'] == wxid:
            return contact['nickname']
    return None  # 如果没有找到对应的wxid，则返回None


def get_display_name_or_nickname(room_members, group_wxid, wxid):
    if group_wxid in room_members:
        for member in room_members[group_wxid]['member_list']:
            if member['wxid'] == wxid:
                return member['display_name'] if member['display_name'] else member['nickname']
    return None  # 如果没有找到对应的group_wxid或wxid，则返回None


class NtchatMessage(ChatMessage):
    def __init__(self, wechat, wechat_msg, self_id, self_name, is_group=False):
        try:
            super().__init__(wechat_msg)
            if 'msgid' in wechat_msg['data']:
                self.msg_id = wechat_msg['data']['msgid']
            else:
                self.msg_id = str(int(time.time()))

            self.create_time = wechat_msg['data'].get("timestamp", int(time.time()))

            self.is_group = is_group
            self.wechat = wechat

            # 获取一些可能多次使用的值
            current_dir = os.getcwd()

            # 从文件读取数据，并构建以 wxid 为键的字典
            with open(os.path.join(current_dir, "tmp", 'wx_contacts.json'), 'r', encoding='utf-8') as f:
                contacts = {contact['wxid']: contact['nickname'] for contact in json.load(f)}
            with open(os.path.join(current_dir, "tmp", 'wx_rooms.json'), 'r', encoding='utf-8') as f:
                rooms = {room['wxid']: room['nickname'] for room in json.load(f)}

            data = wechat_msg['data']
            self.from_user_id = data.get('from_wxid', data.get("room_wxid"))
            self.from_user_nickname = contacts.get(self.from_user_id)
            if self_id == self.from_user_id:
                self.to_user_id = data.get("to_wxid")
                self.to_user_nickname = contacts.get(self.to_user_id)
                self.other_user_nickname = self.to_user_nickname
                self.other_user_id = self.to_user_id
            else:
                self.to_user_id = self_id
                self.to_user_nickname = self_name
                self.other_user_nickname = self.from_user_nickname
                self.other_user_id = self.from_user_id

            if wechat_msg["type"] == ntchat.MT_RECV_TEXT_MSG:  # 文本消息类型 11046
                self.ctype = ContextType.TEXT
                self.content = data['msg']
            elif wechat_msg["type"] == ntchat.MT_RECV_IMAGE_MSG:  # 图片消息通知 11047
                image_path = data.get('image').replace('\\', '/')
                if ensure_file_ready(image_path):
                    decoder = WechatImageDecoder(image_path)
                    self.ctype = ContextType.IMAGE
                    self.content = decoder.decode()
                    self._prepare_fn = lambda: None
                else:
                    logger.error(f"Image file {image_path} is not ready.")
            elif wechat_msg["type"] == ntchat.MT_RECV_VOICE_MSG:  # 语音消息通知 11048
                self.ctype = ContextType.VOICE
                self.content = data.get('mp3_file')
                self._prepare_fn = lambda: None
            elif wechat_msg["type"] == ntchat.MT_ROOM_ADD_MEMBER_NOTIFY_MSG:  # 群成员新增通知 11098
                self.ctype = ContextType.JOIN_GROUP
                self.actual_user_nickname = data['member_list'][0]['nickname']
                self.content = f"{self.actual_user_nickname}加入了群聊！"
                directory = os.path.join(os.getcwd(), "tmp")
                result = {}
                for room_wxid in rooms.keys():
                    room_members = wechatnt.get_room_members(room_wxid)
                    result[room_wxid] = room_members
                with open(os.path.join(directory, 'wx_room_members.json'), 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)
            elif wechat_msg["type"] == ntchat.MT_RECV_SYSTEM_MSG and "拍了拍我" in data.get('raw_msg'):  # 系统消息通知 11058
                self.ctype = ContextType.PATPAT
                self.content = data.get('raw_msg')
            elif wechat_msg["type"] == ntchat.MT_RECV_FILE_MSG:  # 文件消息通知 11055
                self.ctype = ContextType.FILE
                self.content = data.get('file')
            elif wechat_msg["type"] == ntchat.MT_RECV_VIDEO_MSG:  # 视频消息通知 11051
                self.ctype = ContextType.VIDEO
                self.content = data.get('video')
            elif wechat_msg["type"] in [ntchat.MT_RECV_LINK_MSG, ntchat.MT_RECV_OTHER_APP_MSG]:  # 链接卡片消息通知 MT_RECV_LINK_MSG
                self.ctype = ContextType.SHARING
                self.content = data.get('raw_msg')
                # 定义正则表达式
                url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\$\$,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                
                # 使用re.search()查找url
                url_match = url_pattern.search(self.content)
                
                # 如果找到url，返回url，否则返回None
                if url_match:
                    self.content = url_match.group()

            else:
                self.ctype = ContextType.OTHER
                self.content = ""

            if self.is_group:
                directory = os.path.join(os.getcwd(), "tmp")
                file_path = os.path.join(directory, "wx_room_members.json")
                with open(file_path, 'r', encoding='utf-8') as file:
                    room_members = json.load(file)
                self.other_user_nickname = rooms.get(data.get('room_wxid'))
                self.other_user_id = data.get('room_wxid')
                if self.from_user_id:
                    at_list = data.get('at_user_list', [])
                    self.is_at = self_id in at_list
                    content = data.get('msg', '')
                    pattern = f"@{re.escape(self_name)}(\u2005|\u0020)"
                    self.is_at |= bool(re.search(pattern, content))
                    self.actual_user_id = self.from_user_id
                    if not self.actual_user_nickname:
                        self.actual_user_nickname = get_display_name_or_nickname(room_members, data.get('room_wxid'),
                                                                                 self.from_user_id)
                else:
                    logger.error("群聊消息中没有找到 conversation_id 或 room_wxid")

            logger.debug(f"WechatMessage has been successfully instantiated with message id: {self.msg_id}")
        except Exception as e:
            logger.error(f"在 WechatMessage 的初始化过程中出现错误：{e}")
            raise e
