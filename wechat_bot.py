
# wechat_bot.py
import requests
import json
import configparser
import os
from typing import Optional, List, Dict, Any

class WeChatBot:
    """
    微信企业微信群机器人封装类
    单例模式，确保全局只有一个机器人实例
    """
    _instance = None
    _webhook_url = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WeChatBot, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._load_config()
            self._initialized = True
    
    def _load_config(self) -> None:
        """
        从配置文件加载Webhook配置
        """
        config = configparser.ConfigParser()
        config_file = 'wechat_config.cfg'
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(config_file):
            print(f"配置文件 {config_file} 不存在，创建默认配置文件...")
            config['wechat'] = {
                'webhook_key': '6',
                'webhook_base_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='
            }
            
            with open(config_file, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            print(f"已创建默认配置文件 {config_file}，请修改其中的webhook_key为您的实际Webhook密钥")
        
        # 读取配置文件
        config.read(config_file, encoding='utf-8')
        
        try:
            webhook_key = config.get('wechat', 'webhook_key')
            webhook_base_url = config.get('wechat', 'webhook_base_url')
            self._webhook_url = f"{webhook_base_url}?key={webhook_key}"
            print("Webhook配置加载成功")
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            print(f"配置文件格式错误: {e}")
            self._webhook_url = None
    
    def send_text(self, 
                 content: str, 
                 mentioned_list: Optional[List[str]] = None,
                 mentioned_mobile_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        发送文本消息到企业微信群机器人[1,2](@ref)
        
        Parameters:
        -----------
        content : str
            文本内容
        mentioned_list : List[str], optional
            要@的用户的userid列表，如["zhangsan", "lisi"]，"@all"表示@所有人
        mentioned_mobile_list : List[str], optional  
            要@的用户的手机号列表，如["13800000000"]，"@all"表示@所有人
            
        Returns:
        --------
        Dict[str, Any]
            微信API返回结果
        """
        if self._webhook_url is None:
            return {"errcode": -1, "errmsg": "Webhook URL未配置"}
        
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
            response = requests.post(self._webhook_url, headers=headers, 
                                   data=json.dumps(data), timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                print("微信消息发送成功！")
            else:
                print(f"微信消息发送失败: {result.get('errmsg')}")
            return result
            
        except Exception as e:
            print(f"微信消息发送请求出错: {e}")
            return {"errcode": -1, "errmsg": str(e)}
    
    def send_markdown(self, content: str) -> Dict[str, Any]:
        """
        发送Markdown格式消息[3](@ref)
        
        Parameters:
        -----------
        content : str
            Markdown格式内容
            
        Returns:
        --------
        Dict[str, Any]
            微信API返回结果
        """
        if self._webhook_url is None:
            return {"errcode": -1, "errmsg": "Webhook URL未配置"}
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        try:
            response = requests.post(self._webhook_url, headers=headers,
                                   data=json.dumps(data), timeout=10)
            return response.json()
        except Exception as e:
            print(f"Markdown消息发送失败: {e}")
            return {"errcode": -1, "errmsg": str(e)}
    
    def send_news(self, 
                  articles: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        发送图文消息[4](@ref)
        
        Parameters:
        -----------
        articles : List[Dict[str, str]]
            图文消息列表，每个article包含title, description, url, picurl等字段
            
        Returns:
        --------
        Dict[str, Any]
            微信API返回结果
        """
        if self._webhook_url is None:
            return {"errcode": -1, "errmsg": "Webhook URL未配置"}
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "news",
            "news": {
                "articles": articles
            }
        }
        
        try:
            response = requests.post(self._webhook_url, headers=headers,
                                   data=json.dumps(data), timeout=10)
            return response.json()
        except Exception as e:
            print(f"图文消息发送失败: {e}")
            return {"errcode": -1, "errmsg": str(e)}
    
    def is_available(self) -> bool:
        """
        检查机器人是否可用（Webhook URL已配置）
        
        Returns:
        --------
        bool
            是否可用
        """
        return self._webhook_url is not None

# 创建全局实例
wechat_bot = WeChatBot()

# 便捷函数接口 - 其他模块直接导入这些函数使用[5](@ref)
def send_text(content: str, 
              mentioned_list: Optional[List[str]] = None,
              mentioned_mobile_list: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    发送文本消息的便捷函数[1](@ref)
    
    Parameters:
    -----------
    content : str
        文本内容
    mentioned_list : List[str], optional
        要@的用户列表
    mentioned_mobile_list : List[str], optional  
        要@的用户手机号列表
        
    Returns:
    --------
    Dict[str, Any]
        发送结果
    """
    return wechat_bot.send_text(content, mentioned_list, mentioned_mobile_list)

def send_markdown(content: str) -> Dict[str, Any]:
    """
    发送Markdown消息的便捷函数
    
    Parameters:
    -----------
    content : str
        Markdown内容
        
    Returns:
    --------
    Dict[str, Any]
        发送结果
    """
    return wechat_bot.send_markdown(content)

def send_news(articles: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    发送图文消息的便捷函数
    
    Parameters:
    -----------
    articles : List[Dict[str, str]]
        图文消息列表
        
    Returns:
    --------
    Dict[str, Any]
        发送结果
    """
    return wechat_bot.send_news(articles)

def check_bot_availability() -> bool:
    """
    检查机器人可用性的便捷函数
    
    Returns:
    --------
    bool
        是否可用
    """
    return wechat_bot.is_available()

# 使用示例和测试
if __name__ == '__main__':
    # 测试文本消息发送
    result = send_text("大家好，这是一条测试消息！")
    print(f"发送结果: {result}")
    
    # 测试Markdown消息
    markdown_content = """
    # 标题
    - 项目1: 完成情况 ✅
    - 项目2: 进行中 ⏳
    - 项目3: 未开始 ❌
    """
    result = send_markdown(markdown_content)
    print(f"Markdown发送结果: {result}")
    
    # 测试图文消息
    articles = [
        {
            "title": "今日行情报告",
            "description": "ETH/USDT 最新价格分析",
            "url": "https://example.com/report",
            "picurl": "https://example.com/image.jpg"
        }
    ]
    result = send_news(articles)
    print(f"图文消息发送结果: {result}")