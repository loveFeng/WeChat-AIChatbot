"""
channel factory
"""


def create_channel(channel_type):
    """
    create a channel instance
    :param channel_type: channel type code
    :return: channel instance
    """

    from channel.wechatnt.ntchat_channel import NtchatChannel
    return NtchatChannel()

    raise RuntimeError
