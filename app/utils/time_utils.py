#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""时间工具函数，用于处理时区转换和格式化"""

from datetime import datetime, timezone


def utc_to_local_datetime(utc_datetime):
    """
    将UTC时间转换为本地时间
    
    Args:
        utc_datetime: UTC时区的datetime对象
        
    Returns:
        datetime: 转换后的本地时区datetime对象
    """
    if not utc_datetime:
        return None
    
    # 确保输入是datetime对象
    if not isinstance(utc_datetime, datetime):
        raise TypeError("输入必须是datetime对象")
    
    # 如果datetime没有时区信息，假设它是UTC时间
    if utc_datetime.tzinfo is None:
        # 给UTC时间添加时区信息
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    
    # 转换为本地时间
    return utc_datetime.astimezone()


def format_datetime_with_timezone(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    格式化datetime对象，自动处理时区转换
    
    Args:
        dt: datetime对象（UTC或带时区信息）
        format_str: 格式化字符串，默认为'%Y-%m-%d %H:%M:%S'
        
    Returns:
        str: 格式化后的时间字符串
    """
    if not dt:
        return ''
    
    # 转换为本地时间
    local_dt = utc_to_local_datetime(dt)
    
    # 格式化时间
    return local_dt.strftime(format_str)


def format_datetime_for_frontend(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    为前端格式化时间，返回包含时区信息的完整格式
    
    Args:
        dt: datetime对象
        format_str: 基本格式化字符串
        
    Returns:
        str: 格式化后的时间字符串，包含时区信息
    """
    if not dt:
        return ''
    
    local_dt = utc_to_local_datetime(dt)
    formatted_time = local_dt.strftime(format_str)
    
    # 获取时区名称或偏移
    tz_name = local_dt.tzname() or f"UTC{local_dt.strftime('%z')}"
    
    return f"{formatted_time} {tz_name}"
