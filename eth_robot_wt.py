# main.py
import time
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from wechat_bot import send_text
from bn_eth import get_eth_data
from wavetrend import calculate_wavetrend

# 全局变量
last_alert_sent_time = None
ALERT_COOLDOWN_MINUTES = 30  # 警报冷却时间30分钟

# BN链接状态相关全局变量
bn_connection_ok = True  # BN链接状态，初始为True
bn_failure_count = 0     # BN链接失败次数统计
bn_last_check_time = None  # 最后一次检查时间

def should_suppress_message():
    """
    检查当前时间是否在消息抑制时间段内（北京时间1:00-7:00）
    Returns:
        bool: True表示需要抑制消息发送，False表示允许发送
    """
    try:
        # 获取当前时间（使用服务器本地时间，假设服务器已设置为北京时间）
        now = datetime.now()
        current_time = now.time()
        
        # 定义抑制时间段：1:00-7:00（包括1:00，不包括7:00）
        suppress_start = time(1, 0, 0)  # 01:00:00
        suppress_end = time(7, 0, 0)     # 07:00:00
        
        # 检查当前时间是否在抑制时间段内
        if suppress_start <= current_time < suppress_end:
            print(f"当前时间 {current_time.strftime('%H:%M:%S')} 在抑制时间段内（1:00-7:00），跳过消息发送")
            return True
        return False
    except Exception as e:
        print(f"检查抑制时间时出错: {e}")
        return False  # 出错时允许发送，避免因时间检查失败而丢失重要消息

def send_startup_message():
    """发送启动消息"""
    try:
        # 检查是否在抑制时间段
        if should_suppress_message():
            print("启动消息：当前处于抑制时间段，消息发送已跳过")
            return
            
        message = "🚀 曼波机器人启动成功！开始监控ETH/USDT WaveTrend指标（15秒间隔）"
        result = send_text(message)
        if result and result.get('errcode') == 0:
            print("启动消息发送成功")
        else:
            print("启动消息发送可能失败")
    except Exception as e:
        print(f"发送启动消息时出错: {e}")

def update_bn_connection_status(success):
    """
    更新BN链接状态和失败次数统计
    
    Parameters:
    -----------
    success : bool
        本次链接是否成功
    """
    global bn_connection_ok, bn_failure_count, bn_last_check_time
    
    bn_last_check_time = datetime.now()
    
    if success:
        bn_connection_ok = True
        bn_failure_count = 0  # 成功时重置失败计数
    else:
        bn_connection_ok = False
        bn_failure_count += 1

def check_wavetrend_alert():
    """
    每15秒检查WaveTrend指标，满足条件时发送警报
    同时更新BN链接状态标志位
    """
    global last_alert_sent_time
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在获取ETH数据并计算WaveTrend...")
        
        # 获取ETH数据（这里直接更新标志位）
        df = get_eth_data('30m', 100)
        
        # 在数据获取后立即更新BN链接状态（无额外线程）
        if df is None or df.empty:
            print("获取ETH数据失败")
            update_bn_connection_status(False)
            return
        else:
            update_bn_connection_status(True)
        
        # 计算WaveTrend指标
        wt1, wt2 = calculate_wavetrend(df)
        current_price = df['close'].iloc[-1]
        
        print(f"最新数据 - 价格: {current_price:.2f}, WT1: {wt1:.2f}, WT2: {wt2:.2f}")
        
        # 检查是否需要发送警报
        current_time = datetime.now()
        should_send_alert = False
        alert_message = ""
        
        if wt1 > 49:
            alert_message = f"🐶 哈基米，WT1是{wt1:.2f}（当前价格: {current_price:.2f}）"
            should_send_alert = True
        elif wt1 < -49:
            alert_message = f"🌊 曼波，WT1是{wt1:.2f}（当前价格: {current_price:.2f}）"
            should_send_alert = True
        
        # 检查冷却时间
        if should_send_alert:
            if last_alert_sent_time is None:
                # 第一次发送警报
                send_alert_with_cooldown(alert_message, current_time)
            else:
                time_diff = current_time - last_alert_sent_time
                if time_diff.total_seconds() >= ALERT_COOLDOWN_MINUTES * 60:
                    send_alert_with_cooldown(alert_message, current_time)
                else:
                    remaining_time = ALERT_COOLDOWN_MINUTES * 60 - time_diff.total_seconds()
                    print(f"警报冷却中，{int(remaining_time/60)}分{int(remaining_time%60)}秒后可再次发送")
        
    except Exception as e:
        print(f"检查WaveTrend时出错: {e}")
        update_bn_connection_status(False)

def send_alert_with_cooldown(message, current_time):
    """发送警报并更新最后发送时间"""
    global last_alert_sent_time
    
    # 检查是否在抑制时间段
    if should_suppress_message():
        print(f"警报抑制：当前处于抑制时间段，跳过警报发送: {message}")
        return
        
    try:
        result = send_text(message)
        if result and result.get('errcode') == 0:
            last_alert_sent_time = current_time
            print(f"警报发送成功: {message}")
        else:
            print(f"警报发送可能失败")
    except Exception as e:
        print(f"发送警报时出错: {e}")

def test_bn_connection():
    """
    测试BN链接状态（用于每日报告）
    Returns:
        tuple: (连接状态, 附加信息, 最新价格)
    """
    try:
        # 尝试获取少量数据测试连接
        df = get_eth_data('1m', 2)
        if df is not None and not df.empty:
            latest_price = df['close'].iloc[-1]
            return True, f"最新价格: {latest_price:.2f} USDT，数据更新时间: {df.index[-1].strftime('%H:%M:%S')}", latest_price
        else:
            return False, "获取数据失败，返回空数据", None
    except Exception as e:
        return False, f"连接异常: {str(e)}", None

def send_daily_status():
    """每天9:00发送状态消息，检查BN链接状态并报告失败次数"""
    global bn_failure_count
    
    # 检查是否在抑制时间段（虽然9:00不在抑制时间段，但为保险起见还是检查）
    if should_suppress_message():
        print("每日状态报告：当前处于抑制时间段，报告发送已跳过")
        # 注意：即使跳过发送，我们仍然重置失败计数，避免累积
        bn_failure_count = 0
        return
        
    try:
        print("生成每日状态报告...")
        
        # 测试BN链接状态
        is_connected, connection_info, latest_price = test_bn_connection()
        status = "正常" if is_connected else "异常"
        
        # 生成状态消息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_check_time = bn_last_check_time.strftime("%H:%M:%S") if bn_last_check_time else "从未检查"
        
        message = f"""📅 每日状态报告 - {current_time}

🤖 曼波机器人运行状态
🔗 与币安链接: {status}
📊 连接信息: {connection_info}
❌ 昨日失败次数: {bn_failure_count}次
🕒 最后检查: {last_check_time}
⏰ 检查频率: 每15秒一次
🌙 消息抑制: 北京时间1:00-7:00不发送

💡 系统状态: {'✅ 一切正常' if is_connected else '⚠️ 需要检查'}
📈 重置统计: 失败次数已清零
🕒 下次报告: 明日09:00"""
        
        # 发送消息
        result = send_text(message)
        if result and result.get('errcode') == 0:
            print("每日状态消息发送成功")
            # 重置失败次数
            bn_failure_count = 0
        else:
            print("每日状态消息发送可能失败")
            
    except Exception as e:
        print(f"发送每日状态消息时出错: {e}")

def get_bn_connection_stats():
    """
    获取BN连接统计信息
    Returns:
        dict: 包含连接状态和统计信息的字典
    """
    return {
        'connection_ok': bn_connection_ok,
        'failure_count': bn_failure_count,
        'last_check_time': bn_last_check_time
    }

def main():
    """主函数"""
    print("=" * 60)
    print("曼波机器人启动初始化...")
    print("=" * 60)
    
    # 发送启动消息
    send_startup_message()
    
    # 设置调度器（使用北京时间）
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
    
    # 每15秒执行WaveTrend检查（修改为15秒间隔）
    scheduler.add_job(
        check_wavetrend_alert,
        'interval',
        seconds=15,  # 改为15秒间隔
        id='wavetrend_check',
        next_run_time=datetime.now()  # 立即开始
    )
    
    # 每天9:00发送状态报告（北京时间）
    scheduler.add_job(
        send_daily_status,
        CronTrigger(hour=9, minute=0, timezone='Asia/Shanghai'),
        id='daily_status'
    )
    
    try:
        # 启动调度器
        scheduler.start()
        print("调度器启动成功")
        print("• 每15秒检查WaveTrend指标")
        print("• 每天09:00发送状态报告（北京时间）")
        print("• WT1阈值: >49 或 <-49")
        print("• 警报冷却时间: 30分钟")
        print("• 消息抑制: 北京时间1:00-7:00不发送消息")
        print("• BN状态检测: 集成在数据获取中（无额外线程）")
        print("=" * 60)
        
        # 保持主程序运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭程序...")
    except Exception as e:
        print(f"程序运行出错: {e}")
    finally:
        if 'scheduler' in locals() and scheduler.running:
            scheduler.shutdown()
        
        # 发送最终统计报告（关闭报告不受抑制时间限制）
        stats = get_bn_connection_stats()
        final_report = f"""🔴 曼波机器人已关闭
运行统计:
• BN连接最终状态: {'正常' if stats['connection_ok'] else '异常'}
• 总失败次数: {stats['failure_count']}
• 最后运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• 运行模式: 15秒间隔检测
• 消息抑制: 北京时间1:00-7:00不发送消息"""
        
        try:
            # 关闭报告不受时间抑制限制，始终发送
            send_text(final_report)
            print("关闭报告已发送")
        except:
            print("关闭报告发送失败")
        
        print("曼波机器人已关闭")

if __name__ == "__main__":
    main()
