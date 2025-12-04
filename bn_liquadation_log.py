import websockets
import asyncio
import json
import time
import logging
import os
from datetime import datetime, time as dt_time
from collections import deque
from logging.handlers import RotatingFileHandler

# 全局变量
liquidation_records = deque()  # 存储5分钟内的爆仓记录
last_sent_time = 0  # 最后发送时间
WT1_value = 50  # WT1值
TIME_WINDOW = 300  # 5分钟(秒)
COOLDOWN = 900  # 15分钟冷却(秒)
THRESHOLD = 500000  # 50万美元阈值


# 在现有全局变量部分添加以下变量
script_start_time = time.time()  # 脚本启动时间
MAX_RUNNING_TIME = 24 * 60 * 60  # 24小时（以秒为单位）
shutdown_event = asyncio.Event()  # 关机事件标志


# 配置日志系统
def setup_logging():
    """配置日志系统，将日志记录到haqi.log文件"""
    # 创建logs目录如果不存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "haqi.log")
    
    # 创建logger
    logger = logging.getLogger("haqi_monitor")
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 创建RotatingFileHandler，限制单个文件大小为5MB，保留3个备份
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        
        # 设置日志格式 - 包含毫秒级时间戳
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # 同时添加控制台处理器（可选）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# 初始化日志记录器
haqi_logger = setup_logging()

async def get_eth_liquidations():
    ws_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    retry_delay = 5  # 初始重连延迟，单位：秒
    max_retry_delay = 300  # 最大重连延迟，例如5分钟

    while True:  # 使用循环而非递归
        try:
            async with websockets.connect(ws_url) as websocket:
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
                        break  # 跳出内部接收循环，外部循环会重连
                    except Exception as e:
                        # 可以选择继续监听下一条消息，而不是立即重连
                        continue

        except (websockets.exceptions.InvalidURI, 
                websockets.exceptions.InvalidHandshake) as e:
            haqi_logger.error(f"连接参数问题，无法建立连接: {e}")
            break  # 这类错误通常无法通过重连解决，退出循环
        except (OSError, asyncio.TimeoutError, 
                websockets.exceptions.WebSocketException) as e:
            haqi_logger.warning(f"没有获取到爆仓事件（{e}），{retry_delay}秒后尝试重连...")
        except Exception as e:
            haqi_logger.error(f"监控过程中发生未预期的错误: {e}")
        
        await asyncio.sleep(retry_delay)

def extract_liquidation_data(raw_data):
    """提取ETH爆仓数据"""
    order_data = raw_data.get('o', {})
    symbol = order_data.get('s', '').upper()

    if not symbol.startswith('ETH'):
        return None
    
    quantity = float(order_data.get('q', 0))
    price = float(order_data.get('p', 0))
    timestamp = order_data.get('T', int(time.time() * 1000))
    
    # 记录所有爆仓事件到日志
    event_time = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
    total_value = quantity * price
    
    haqi_logger.info(f"爆仓事件 - 交易对: {symbol}, 方向: {order_data.get('S', 'Unknown')}, "
                    f"数量: {quantity}, 价格: ${price:.2f}, 总价值: ${total_value:,.2f}, 时间: {event_time}")
    
    return {
        'symbol': symbol,
        'quantity': quantity,
        'price': price,
        'total_value': total_value,  # 计算总金额
        'timestamp': timestamp,
        'time_str': event_time
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
        remaining_time = COOLDOWN - (time.time() - last_sent_time)
        return False
    
    # 计算5分钟内爆仓总量
    five_min_ago = time.time() - TIME_WINDOW
    total_5min = current_value + sum(
        record['total_value'] for record in liquidation_records 
        if record['timestamp']/1000 >= five_min_ago
    )
    
    haqi_logger.info(f"5分钟内爆仓总量计算: ${total_5min:,.2f} (阈值: ${THRESHOLD:,.2f})")
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
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建详细的消息，包含发生时间
        message = (f"发生哈气事件，总金额${total_5min:,.2f}，"
                  f"事件时间: {current_time}，"
                  f"交易对: {liquidation_data['symbol']}，"
                  f"5分钟内爆仓总数: {len(liquidation_records)}笔")
        
        # 记录到日志文件（替代原来的微信发送）
        haqi_logger.critical(f"🚨 {message}")
        
        # 同时记录详细统计信息
        haqi_logger.info(f"哈气事件详细统计 - "
                        f"最新爆仓: ${liquidation_data['total_value']:,.2f}, "
                        f"WT1当前值: {WT1_value}, "
                        f"记录队列长度: {len(liquidation_records)}")
        
        last_sent_time = time.time()
        
        # 可选：发送后清空记录，避免重复报警
        # liquidation_records.clear()

async def start_eth_liquidations_monitor():
    """主函数"""
    haqi_logger.info("=" * 60)
    haqi_logger.info("ETH爆仓监控系统启动")
    haqi_logger.info(f"监控参数: 5分钟窗口, 阈值${THRESHOLD:,}, 冷却{COOLDOWN}秒")
    haqi_logger.info(f"当前WT1: {WT1_value}, 抑制时间: 1:00-7:00")
    haqi_logger.info("=" * 60)
    
    await get_eth_liquidations()
async def shutdown_monitor():
    """
    24小时关机监控器
    在后台运行，24小时后触发关机事件
    """
    haqi_logger.info(f"24小时关机监控器已启动，脚本将在24小时后自动关闭")
    
    try:
        # 等待24小时
        await asyncio.sleep(MAX_RUNNING_TIME)
        
        # 24小时到，触发关机事件
        haqi_logger.info("24小时运行时间已到，触发自动关闭")
        shutdown_event.set()
        
    except asyncio.CancelledError:
        haqi_logger.info("关机监控器被取消")
    except Exception as e:
        haqi_logger.error(f"关机监控器出错: {e}")

async def safe_shutdown():
    """
    安全关闭程序
    """
    haqi_logger.info("开始安全关闭程序...")
    
    # 记录运行统计信息
    running_time = time.time() - script_start_time
    hours = running_time / 3600
    haqi_logger.info(f"脚本运行时间: {hours:.2f}小时")
    haqi_logger.info(f"处理的爆仓记录总数: {len(liquidation_records)}")
    
    # 这里可以添加其他清理逻辑，如关闭数据库连接等
    haqi_logger.info("安全关闭程序完成")

async def get_eth_liquidations_with_timeout():
    """
    带超时控制的爆仓数据获取函数
    """
    ws_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    retry_delay = 5

    while not shutdown_event.is_set():  # 检查关机标志
        try:
            haqi_logger.info(f"尝试连接至 {ws_url}...")
            async with websockets.connect(ws_url) as websocket:
                haqi_logger.info("WebSocket 连接成功。")
                retry_delay = 5
                
                # 监听消息循环（增加关机检查）
                while not shutdown_event.is_set():
                    try:
                        # 设置接收超时，以便定期检查关机标志
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)
                            liquidation_data = extract_liquidation_data(data)
                            if liquidation_data:
                                check_and_send_alert(liquidation_data)
                        except asyncio.TimeoutError:
                            # 超时是正常的，用于检查关机标志
                            continue
                            
                    except websockets.exceptions.ConnectionClosed:
                        haqi_logger.warning("WebSocket连接关闭，尝试重连...")
                        break
                    except Exception as e:
                        haqi_logger.error(f"处理消息时出错: {e}")
                        continue

        except (websockets.exceptions.InvalidURI, 
                websockets.exceptions.InvalidHandshake) as e:
            haqi_logger.error(f"连接参数问题: {e}")
            break
        except (OSError, asyncio.TimeoutError, 
                websockets.exceptions.WebSocketException) as e:
            if not shutdown_event.is_set():  # 只有非关机状态才重连
                haqi_logger.warning(f"连接异常，{retry_delay}秒后重连: {e}")
        except Exception as e:
            if not shutdown_event.is_set():
                haqi_logger.error(f"监控过程出错: {e}")
        
        if not shutdown_event.is_set():
            await asyncio.sleep(retry_delay)

async def start_eth_liquidations_monitor():
    """
    修改后的主函数，集成24小时关机功能
    """
    haqi_logger.info("=" * 60)
    haqi_logger.info("ETH爆仓监控系统启动")
    haqi_logger.info(f"监控参数: 5分钟窗口, 阈值${THRESHOLD:,}, 冷却{COOLDOWN}秒")
    haqi_logger.info(f"当前WT1: {WT1_value}, 抑制时间: 1:00-7:00")
    haqi_logger.info(f"最大运行时间: 24小时")
    haqi_logger.info("=" * 60)
    
    # 创建关机监控任务
    shutdown_task = asyncio.create_task(shutdown_monitor())
    
    try:
        # 运行主监控逻辑，直到关机事件触发
        await get_eth_liquidations_with_timeout()
    except asyncio.CancelledError:
        haqi_logger.info("主监控任务被取消")
    finally:
        # 取消关机监控任务
        shutdown_task.cancel()
        try:
            await shutdown_task
        except asyncio.CancelledError:
            pass
        
        # 执行安全关闭
        await safe_shutdown()

async def main_with_timeout():
    """
    新的主入口函数
    """
    # 设置初始WT1值
    set_WT1(50)
    
    # 运行监控系统
    await start_eth_liquidations_monitor()

def get_remaining_time():
    """
    获取剩余运行时间（用于外部查询）
    """
    elapsed = time.time() - script_start_time
    remaining = max(0, MAX_RUNNING_TIME - elapsed)
    return remaining

def force_shutdown():
    """
    强制立即关闭（供外部调用）
    """
    haqi_logger.info("接收到强制关闭信号")
    shutdown_event.set()

if __name__ == "__main__":
    # 设置初始WT1值
    set_WT1(50)
    
    try:
        # 使用新的主函数
        asyncio.run(main_with_timeout())
    except KeyboardInterrupt:
        haqi_logger.info("监控程序被用户中断")
    except Exception as e:
        haqi_logger.error(f"监控程序异常退出: {e}")
    finally:
        haqi_logger.info("ETH爆仓监控系统停止运行")
        
        # 打印最终运行时间
        total_time = time.time() - script_start_time
        hours = total_time / 3600
        haqi_logger.info(f"总运行时间: {hours:.2f}小时")