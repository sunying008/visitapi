#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理诊断和配置工具
"""

import asyncio
import aiohttp
import socket
import requests

def check_proxy_type(proxy_host, proxy_port):
    """检查代理类型"""
    print(f"检查代理 {proxy_host}:{proxy_port}")
    
    try:
        # 尝试连接到代理服务器
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((proxy_host, proxy_port))
        sock.close()
        
        if result == 0:
            print(f"✅ 代理端口 {proxy_port} 可以连接")
            return True
        else:
            print(f"❌ 代理端口 {proxy_port} 无法连接")
            return False
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def test_requests_proxy(proxy_url):
    """使用requests库测试代理"""
    print(f"\n使用requests测试代理: {proxy_url}")
    
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    try:
        # 测试HTTP请求
        response = requests.get(
            'http://httpbin.org/ip', 
            proxies=proxies, 
            timeout=10
        )
        print(f"✅ requests HTTP测试成功")
        print(f"响应: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"❌ requests测试失败: {e}")
        return False

async def test_aiohttp_with_different_configs(proxy_url):
    """测试不同的aiohttp代理配置"""
    print(f"\n测试aiohttp代理配置: {proxy_url}")
    
    # 配置1: 基本代理设置
    print("\n--- 配置1: 基本代理设置 ---")
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                'http://httpbin.org/ip',
                proxy=proxy_url
            ) as response:
                content = await response.text()
                print(f"✅ 基本配置成功: {content.strip()}")
    except Exception as e:
        print(f"❌ 基本配置失败: {e}")
    
    # 配置2: 禁用SSL验证
    print("\n--- 配置2: 禁用SSL验证 ---")
    try:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        ) as session:
            async with session.get(
                'http://httpbin.org/ip',
                proxy=proxy_url
            ) as response:
                content = await response.text()
                print(f"✅ SSL禁用配置成功: {content.strip()}")
    except Exception as e:
        print(f"❌ SSL禁用配置失败: {e}")
    
    # 配置3: SOCKS代理（如果是SOCKS）
    print("\n--- 配置3: 尝试SOCKS代理 ---")
    try:
        # 尝试安装 aiohttp-socks
        import aiohttp_socks
        
        connector = aiohttp_socks.ProxyConnector.from_url(
            proxy_url.replace('http://', 'socks5://')
        )
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        ) as session:
            async with session.get('http://httpbin.org/ip') as response:
                content = await response.text()
                print(f"✅ SOCKS代理成功: {content.strip()}")
    except ImportError:
        print("⚠️  aiohttp-socks未安装，跳过SOCKS测试")
    except Exception as e:
        print(f"❌ SOCKS代理失败: {e}")

def suggest_proxy_config(proxy_port):
    """建议代理配置"""
    print(f"\n=== 代理配置建议 ===")
    
    # 常见代理端口和类型
    common_configs = {
        7890: "Clash (HTTP)",
        7891: "Clash (SOCKS5)", 
        1080: "V2Ray/Shadowsocks (SOCKS5)",
        8080: "HTTP代理",
        3128: "Squid代理",
        8888: "其他HTTP代理"
    }
    
    if proxy_port in common_configs:
        print(f"端口 {proxy_port} 通常是: {common_configs[proxy_port]}")
        
        if proxy_port == 7891 or proxy_port == 1080:
            print("建议配置:")
            print(f"  SOCKS5: socks5://127.0.0.1:{proxy_port}")
            print("  需要安装: pip install aiohttp-socks")
        else:
            print("建议配置:")
            print(f"  HTTP: http://127.0.0.1:{proxy_port}")
    else:
        print(f"端口 {proxy_port} 不是常见代理端口")
        print("建议尝试:")
        print(f"  HTTP: http://127.0.0.1:{proxy_port}")
        print(f"  SOCKS5: socks5://127.0.0.1:{proxy_port}")

if __name__ == "__main__":
    import sys
    
    proxy_host = "127.0.0.1"
    proxy_port = 63763  # 你的代理端口
    
    if len(sys.argv) > 1:
        proxy_port = int(sys.argv[1])
    
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    
    print("=== 代理诊断工具 ===")
    
    # 1. 检查端口连接
    if not check_proxy_type(proxy_host, proxy_port):
        print("代理端口无法连接，请检查代理软件是否运行")
        exit(1)
    
    # 2. 测试requests
    requests_works = test_requests_proxy(proxy_url)
    
    # 3. 测试aiohttp
    asyncio.run(test_aiohttp_with_different_configs(proxy_url))
    
    # 4. 建议配置
    suggest_proxy_config(proxy_port)
    
    if not requests_works:
        print("\n⚠️  代理可能不是HTTP代理，请检查代理类型")
        print("常见解决方案:")
        print("1. 确认代理软件正在运行")
        print("2. 检查代理端口是否正确")
        print("3. 如果是SOCKS代理，需要使用SOCKS协议")
