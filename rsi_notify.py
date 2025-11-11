import ccxt
import pandas as pd
import talib
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from plyer import notification
import logging
import time  # 新增导入，用于添加短暂延迟
import requests  # 确保在文件开头已经导入
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RSINotifierFixedWindow:
    def __init__(self, symbol='ETH/USDT', timeframe='15m', rsi_period=14):
        self.symbol = symbol
        self.timeframe = timeframe
        self.rsi_period = rsi_period
        self.exchange = ccxt.binance({'enableRateLimit': True})
        # 标记当前15分钟窗口内是否已发送过通知
        self.notified_in_current_window = False  
        # 记录当前窗口的起始时间戳（精确到分钟，并规整到15分钟的整数倍）
        self.current_window_start = self.get_current_window_start()
        
        # === 新增：程序启动时发送一次通知 ===
        # 添加一个短暂延迟，确保初始化完全完成
        time.sleep(1)
        self.send_notification(
            "RSI监控器已启动", 
            f"开始监控 {self.symbol} ({self.timeframe}) 的RSI指标。\n监控条件: RSI ≥ 70 或 RSI ≤ 30\n每个15分钟窗口内最多提醒一次。"
        )
        # === 新增代码结束 ===
        
    def get_current_window_start(self):
        """计算当前所属的15分钟窗口的起始时间点"""
        now = datetime.now()
        # 将分钟数规整到15分钟的整数倍（例如0, 15, 30, 45）
        rounded_minute = (now.minute // 15) * 15
        # 构建当前窗口的起始时间（秒和微秒归零）
        window_start = now.replace(minute=rounded_minute, second=0, microsecond=0)
        return window_start

    def check_window_shift(self):
        """检查是否进入了新的15分钟窗口，如果是则重置通知标记"""
        now_window_start = self.get_current_window_start()
        if now_window_start > self.current_window_start:
            # 进入了新的时间窗口
            logger.info(f"进入新的时间窗口: {self.current_window_start} -> {now_window_start}，重置通知标记")
            self.current_window_start = now_window_start
            self.notified_in_current_window = False
            return True
        return False

    def fetch_ohlcv_data(self, limit=100):
        """从币安获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return None

    def calculate_rsi(self, df):
        """计算RSI指标"""
        if len(df) < self.rsi_period:
            logger.warning("数据不足，无法计算RSI")
            return None, df
        
        df['RSI'] = talib.RSI(df['close'], timeperiod=self.rsi_period)
        current_rsi = df['RSI'].iloc[-1]
        return current_rsi, df

    def send_notification(self, title, message):
        def send_notification(self, title, message):
        """
        通过 go-cqhttp 发送群消息
        """
        # API 地址，端口需与 go-cqhttp 配置一致
        api_url = "http://127.0.0.1:5700/send_group_msg"

        # 替换为你的目标 QQ 群号
        group_id = "你的QQ群号"  # 例如 "123456789"

        # 合并 title 和 message 作为发送的内容
        full_message = f"{title}\n{message}"

        payload = {
            "group_id": group_id,
            "message": full_message
        }

        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=5)

            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    logger.info(f"QQ群消息发送成功: {full_message}")
                    return True
                else:
                    logger.error(f"QQ群消息发送失败，API 返回错误: {result.get('wording')}")
                    return False
            else:
                logger.error(f"HTTP 请求失败，状态码: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到 go-cqhttp 服务，请检查其是否正常运行。")
            return False
        except requests.exceptions.Timeout:
            logger.error("发送QQ消息请求超时。")
            return False
        except Exception as e:
            logger.error(f"发送QQ消息时发生未知错误: {e}")
            return False


    def check_and_notify(self):
        """检查RSI条件并在满足条件时发送通知（遵守固定窗口限制）"""
        # 每次检查前，先确认是否进入新窗口
        self.check_window_shift()
        
        logger.info("开始检查RSI...")
        # 获取数据
        df = self.fetch_ohlcv_data()
        if df is None or df.empty:
            logger.warning("未获取到数据，跳过本次检查")
            return

        # 计算RSI
        current_rsi, df_with_rsi = self.calculate_rsi(df)
        if current_rsi is None:
            return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{current_time}] {self.symbol} RSI: {current_rsi:.2f}")

        # 检查RSI条件
        conditions_met = []
        if current_rsi >= 70:
            conditions_met.append(f"RSI过高: {current_rsi:.2f}")
        elif current_rsi <= 30:
            conditions_met.append(f"RSI过低: {current_rsi:.2f}")

        # 如果条件满足且当前窗口内未发送过通知
        if conditions_met and not self.notified_in_current_window:
            title = f"RSI提醒 - {self.symbol}"
            message = f"当前RSI: {current_rsi:.2f}\n"
            message += "\n".join(conditions_met)
            message += f"\n时间: {current_time}"
            message += f"\n时间窗口: {self.current_window_start.strftime('%H:%M')} - {(self.current_window_start + timedelta(minutes=15)).strftime('%H:%M')}"
            
            if self.send_notification(title, message):
                self.notified_in_current_window = True
                logger.info(f"已发送RSI提醒: {conditions_met}，本窗口内将不再提醒")
        elif conditions_met and self.notified_in_current_window:
            logger.info(f"RSI条件满足但本窗口内已发送过通知，跳过提醒")
        else:
            logger.info("RSI条件未满足")

def main():
    # 创建RSI监控器
    notifier = RSINotifierFixedWindow(
        symbol='ETH/USDT',
        timeframe='15m',
        rsi_period=14
    )

    # 创建调度器
    scheduler = BlockingScheduler()

    # 添加定时任务：每分钟检查一次（您可以根据需要调整检查频率，例如每2分钟或5分钟）
    # 触发时间设定为每分钟的第30秒执行，可以适当分散请求
    scheduler.add_job(
        notifier.check_and_notify,
        'cron',
        second=30,
        id='rsi_check'
    )

    # 添加一个每15分钟整点打印窗口信息的任务（可选，用于观察窗口切换）
    scheduler.add_job(
        lambda: logger.info(f"当前窗口起始: {notifier.current_window_start.strftime('%H:%M')}, 窗口内已通知: {notifier.notified_in_current_window}"),
        'cron',
        minute='0,15,30,45',
        second=0,
        id='window_info'
    )

    try:
        logger.info("启动RSI监控器（固定窗口模式）...")
        logger.info("监控条件: RSI ≥ 70 或 RSI ≤ 30")
        logger.info("通知规则: 每个15分钟时间窗口内最多提醒一次")
        logger.info("程序运行中，按 Ctrl+C 退出")
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("监控程序被用户中断")
    except Exception as e:
        logger.error(f"监控程序出错: {e}")
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    main()