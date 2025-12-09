import websockets
import asyncio
import json
import time
from datetime import datetime, time as dt_time
from collections import deque
from wechat_bot import send_text

# 全局变量
liquidation_records = deque()  # 存储5分钟内的爆仓记录

last_sent_time = 0  # 最后发送时间
WT1_value = 50  # WT1值
TIME_WINDOW = 300  # 5分钟(秒)
COOLDOWN = 1800  # 30分钟冷却(秒)
THRESHOLD = 250000  # 50万美元阈值

async def get_eth_liquidations():
    ws_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    retry_delay = 10  # 初始重连延迟，单位：秒
    max_retry_delay = 300  # 最大重连延迟，例如5分钟

    while True:  # 使用循环而非递归
        try:
            print(f"尝试连接至 {ws_url}...")
            async with websockets.connect(ws_url) as websocket:
                print("WebSocket 连接成功。")
                retry_delay = 5  # 连接成功后重置重连延迟
                
                # 监听消息循环
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        liquidation_data = extract_liquidation_data(data)
                        if liquidation_data:
                            check_and_send_alert(liquidation_data)
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket 连接在接收数据时被关闭，尝试重新建立连接...")
                        break  # 跳出内部接收循环，外部循环会重连
                    except Exception as e:
                        print(f"处理消息时出错: {e}")
                        # 可以选择继续监听下一条消息，而不是立即重连
                        continue

        except (websockets.exceptions.InvalidURI, 
                websockets.exceptions.InvalidHandshake) as e:
            print(f"连接参数问题，无法建立连接: {e}")
            break  # 这类错误通常无法通过重连解决，退出循环
        except (OSError, asyncio.TimeoutError, 
                websockets.exceptions.WebSocketException) as e:
            print(f"没有获取到爆仓事件（{e}），{retry_delay}秒后尝试重连...")
        except Exception as e:
            print(f"监控过程中发生未预期的错误: {e}")
        
        await asyncio.sleep(retry_delay)
        

def extract_liquidation_data(raw_data):
    """提取ETH爆仓数据"""
    order_data = raw_data.get('o', {})
    symbol = order_data.get('s', '').upper()

    
    if not symbol.startswith('ETHUSDT'):
        return None
    
    quantity = float(order_data.get('q', 0))
    price = float(order_data.get('p', 0))
    timestamp = order_data.get('T', int(time.time() * 1000))
    
    return {
        'symbol': symbol,
        'quantity': quantity,
        'price': price,
        'total_value': quantity * price,  # 计算总金额
        'timestamp': timestamp,
        'time_str': datetime.fromtimestamp(timestamp/1000).strftime('%H:%M:%S')
    }

def set_WT1(value):
    """设置WT1的值"""
    global WT1_value
    WT1_value = value

def is_suppress_time():
    """检查是否在消息抑制时间段(1:00-7:00)"""
    current_time = datetime.now().time()
    return dt_time(1, 0) <= current_time < dt_time(7, 0)

def should_send_alert(current_value):
    """判断是否满足发送条件"""
    if is_suppress_time():
        return False
    
    if not (WT1_value > 49 or WT1_value < -49):
        return False
    
    if time.time() - last_sent_time < COOLDOWN:
        return False
    
    # 计算5分钟内爆仓总量
    five_min_ago = time.time() - TIME_WINDOW
    total_5min = current_value + sum(
        record['total_value'] for record in liquidation_records 
        if record['timestamp']/1000 >= five_min_ago
    )
    return total_5min > THRESHOLD

def check_and_send_alert(liquidation_data):
    """检查条件并发送警报"""
    global last_sent_time, liquidation_records
    
    # 添加当前记录
    liquidation_records.append(liquidation_data)
    
    # 清理5分钟前的记录
    five_min_ago = time.time() - TIME_WINDOW
    while (liquidation_records and 
           liquidation_records[0]['timestamp']/1000 < five_min_ago):
        liquidation_records.popleft()
    
    # 检查发送条件
    if should_send_alert(liquidation_data['total_value']):
        total_5min = sum(record['total_value'] for record in liquidation_records)
        message = f"发生哈气事件，总金额${total_5min:,.2f}"
        
        # 发送微信消息
        
        send_text(message)
        
        last_sent_time = time.time()

async def start_eth_liquidations_monitor():
    """主函数"""
    await get_eth_liquidations()

if __name__ == "__main__":
    asyncio.run(start_eth_liquidations_monitor())