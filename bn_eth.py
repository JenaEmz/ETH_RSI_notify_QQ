# bn_eth.py
import pandas as pd
import requests
import numpy as np
from typing import Optional

def get_eth_data(interval: str = '30m', limit: int = 500) -> Optional[pd.DataFrame]:
    """
    获取ETH/USDT的K线数据（简化版）
    
    Parameters:
    -----------
    interval : str, default='30m'
        K线时间单位，可选: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    limit : int, default=500
        获取的数据条数，最大1000
        
    Returns:
    --------
    pd.DataFrame or None
        包含OHLCV数据的DataFrame，失败返回None
    """
    # 参数验证
    valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
    if interval not in valid_intervals:
        print(f"错误: 时间单位 {interval} 不支持，请使用: {valid_intervals}")
        return None
    
    if limit > 1000:
        print("警告: limit参数最大为1000，已自动调整")
        limit = 1000
    
    # 币安API端点
    base_url = "https://api.binance.com/api/v3/klines"
    
    params = {
        'symbol': 'ETHUSDT',
        'interval': interval,
        'limit': limit
    }
    
    try:
        # 发送请求
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 转换为DataFrame
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ]
        
        df = pd.DataFrame(data, columns=columns)
        
        # 数据类型转换
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])
        
        # 时间戳转换
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        
        # 按时间正序排列
        df.sort_index(inplace=True)
        
        # 只返回需要的列
        result_df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        
        print(f"成功获取 {len(result_df)} 条 {interval} K线数据")
        print(f"时间范围: {result_df.index[0]} 到 {result_df.index[-1]}")
        
        return result_df
        
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except Exception as e:
        print(f"数据处理错误: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    # 获取最近500条30分钟数据
    df = get_eth_data('30m', 500)
    
    if df is not None:
        print(f"数据预览:")
        print(df.head())
        print(f"\n数据统计:")
        print(f"最新价格: {df['close'].iloc[-1]:.2f}")
        print(f"最高价: {df['high'].max():.2f}")
        print(f"最低价: {df['low'].min():.2f}")
        print(f"平均成交量: {df['volume'].mean():.2f}")