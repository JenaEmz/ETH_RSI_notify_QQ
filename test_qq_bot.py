import requests
import json
import configparser
import os

def send_wechat_text(webhook_url, content, mentioned_list=None, mentioned_mobile_list=None):
    """
    发送文本消息到企业微信群机器人
    :param webhook_url: 机器人的Webhook URL
    :param content: 文本内容
    :param mentioned_list: 要@的用户的userid列表，如["zhangsan", "lisi"]，"@all"表示@所有人
    :param mentioned_mobile_list: 要@的用户的手机号列表，如["13800000000"]，"@all"表示@所有人
    """
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list or [],
            "mentioned_mobile_list": mentioned_mobile_list or []
        }
    }
    
    try:
        response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
        result = response.json()
        # 判断是否发送成功，errcode为0表示成功
        if result.get('errcode') == 0:
            print("消息发送成功！")
        else:
            print(f"消息发送失败: {result.get('errmsg')}")
        return result
    except Exception as e:
        print(f"请求出错: {e}")

def load_config():
    """
    从config.cfg配置文件加载配置
    :return: 配置字典
    """
    config = configparser.ConfigParser()
    
    # 如果配置文件不存在，创建默认配置
    if not os.path.exists('config.cfg'):
        print("配置文件不存在，创建默认配置文件...")
        config['wechat'] = {
            'key': '6980d0f2-1e6e-4aaa-8dc9-84962ca56b23'
        }
        with open('config.cfg', 'w') as configfile:
            config.write(configfile)
        print("已创建默认配置文件 config.cfg，请修改其中的key为您的实际Webhook密钥")
    
    # 读取配置文件
    config.read('config.cfg')
    
    # 获取配置项
    try:
        key = config.get('wechat', 'key')
        return key
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("配置文件格式错误，请确保存在 [wechat] 节和 key 选项")
        return None

# 使用方法
if __name__ == '__main__':
    # 从配置文件读取key
    key = load_config()
    
    if key:
        # 构建完整的webhook URL
        webhook = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
        
        # 发送消息
        send_wechat_text(webhook, "大家好，这是一条从配置文件读取密钥的测试消息！")
    else:
        print("无法获取Webhook密钥，请检查配置文件")