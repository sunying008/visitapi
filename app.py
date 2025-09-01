from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import pytz
import logging
import traceback
import asyncio
import aiohttp
import requests
import tempfile
import os
import aiohttp
from bs4 import BeautifulSoup
import base64
import json
import time
import os
import sys
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urljoin

# Fix for Playwright on Windows:
# https://github.com/microsoft/playwright-python/issues/1342
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    from config import NETWORK_CONFIG, CONTENT_CONFIG, SERVICE_CONFIG, LOG_CONFIG
except ImportError:
    # 如果配置文件不存在，使用默认配置
    NETWORK_CONFIG = {
        "timeout": {"connect": 15, "read": 60},
        "retries": {"max_attempts": 3, "delay_factor": 2},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    CONTENT_CONFIG = {
        "max_length": {"default": 10000, "min": 100, "max": 50000},
        "parallel_limit": 10
    }
    SERVICE_CONFIG = {"host": "0.0.0.0", "port": 8001}
    LOG_CONFIG = {"level": "DEBUG"}

# 配置日志
log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f'visitapi_{log_timestamp}.log'

logging.getLogger().handlers.clear()

file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.info(f"Visit API starting up - Logging to file: {log_filename}")

app = FastAPI(
    title="Visit API - Page Access Service",
    version="1.0.0",
    description="""
    ## Visit API - 网页访问服务

    基于 Jina AI MCP 接口设计的页面访问服务，提供网页内容提取、分析和处理功能。

    ### 主要功能
    * **read_url** - 提取网页的干净内容
    * **parallel_read** - 并行读取多个网页
    * **screenshot** - 网页截图功能 
    * **analyze_datetime** - 分析网页发布/更新时间
    * **search** - 网络搜索功能
    * **health** - 服务健康检查
    * **primer** - 系统上下文信息

    ### 使用方法
    1. 在下方选择要测试的 API 端点
    2. 填写必要的参数
    3. 点击 "Try it out" 按钮
    4. 点击 "Execute" 执行请求
    5. 查看返回结果

    ### 支持的网站类型
    - 新闻网站
    - 博客文章
    - 维基百科
    - 知乎文章
    - 技术文档
    - 大多数静态网页

    """,
    contact={
        "name": "Visit API Support",
        "email": "support@visitapi.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# 应用启动时初始化Playwright
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Playwright...")
    app.state.playwright = await async_playwright().start()
    proxy_config = NETWORK_CONFIG.get("proxy", {})
    proxy_url = proxy_config.get("https") or proxy_config.get("http")
    
    launch_options = {
        "headless": True,
        "args": [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
    
    if proxy_url:
        logger.info(f"Playwright using proxy: {proxy_url}")
        launch_options["proxy"] = {"server": proxy_url}
        
    app.state.browser = await app.state.playwright.chromium.launch(**launch_options)
    logger.info("Playwright started successfully.")

# 应用关闭时清理Playwright资源
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Playwright...")
    if hasattr(app.state, 'browser') and app.state.browser.is_connected():
        await app.state.browser.close()
    if hasattr(app.state, 'playwright'):
        await app.state.playwright.stop()
    logger.info("Playwright shut down successfully.")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class ReadUrlRequest(BaseModel):
    url: str
    include_images: Optional[bool] = False
    include_links: Optional[bool] = False
    max_content_length: Optional[int] = 10000

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "include_images": True,
                "include_links": True,
                "max_content_length": 5000
            }
        }
    }

class ScreenshotRequest(BaseModel):
    url: str
    width: Optional[int] = 1280
    height: Optional[int] = 720
    full_page: Optional[bool] = False
    format: Optional[str] = "png"

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.example.com",
                "width": 1280,
                "height": 720,
                "full_page": False,
                "format": "png"
            }
        }
    }

class ParallelReadRequest(BaseModel):
    urls: List[str]
    include_images: Optional[bool] = False
    include_links: Optional[bool] = False
    max_content_length: Optional[int] = 10000

    model_config = {
        "json_schema_extra": {
            "example": {
                "urls": [
                    "https://en.wikipedia.org/wiki/Machine_learning",
                    "https://en.wikipedia.org/wiki/Deep_learning",
                    "https://en.wikipedia.org/wiki/Natural_language_processing"
                ],
                "include_images": False,
                "include_links": True,
                "max_content_length": 3000
            }
        }
    }

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 10
    language: Optional[str] = "en"

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "artificial intelligence latest news",
                "max_results": 10,
                "language": "en"
            }
        }
    }

class DatetimeAnalysisRequest(BaseModel):
    url: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://news.ycombinator.com/item?id=123456"
            }
        }
    }

# 响应模型
class PageContent(BaseModel):
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    clean_text: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None
    images: Optional[List[Dict[str, str]]] = None
    links: Optional[List[Dict[str, str]]] = None
    extraction_status: str
    error: Optional[str] = None
    timestamp: str

class ScreenshotResponse(BaseModel):
    url: str
    screenshot_base64: Optional[str] = None
    width: int
    height: int
    format: str
    error: Optional[str] = None
    timestamp: str

class DatetimeInfo(BaseModel):
    url: str
    published_date: Optional[str] = None
    updated_date: Optional[str] = None
    detected_dates: Optional[List[str]] = None
    confidence: Optional[float] = None
    method: Optional[str] = None
    error: Optional[str] = None

class ApiResponse(BaseModel):
    code: int = 200
    log_id: str
    msg: Optional[str] = None
    data: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    timestamp: str

# 日志中间件
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    return response

# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error handler caught: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "log_id": datetime.now().strftime('%Y%m%d%H%M%S'),
            "msg": str(exc),
            "data": None,
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "traceback": traceback.format_exc() if logging.getLogger().level == logging.DEBUG else None
        }
    )

# 工具函数
def format_timestamp() -> str:
    """返回UTC时间戳"""
    return datetime.now(pytz.UTC).isoformat()

async def extract_content_with_playwright(browser, url: str, include_images: bool, include_links: bool, max_length: int) -> PageContent:
    """使用Playwright提取内容（适用于需要JS渲染或反爬虫强的网站）"""
    logger.info(f"Using shared Playwright browser for {url}")
    
    # 为每个请求创建独立的浏览器上下文
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        # 增加页面加载超时
        await page.goto(url, timeout=NETWORK_CONFIG["timeout"].get("read", 60) * 1000, wait_until='domcontentloaded')
        
        # 等待一段时间让动态内容加载
        await asyncio.sleep(3) 
        
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        return process_soup_content(soup, url, include_images, include_links, max_length)
        
    except PlaywrightTimeoutError:
        logger.error(f"Playwright timed out loading page: {url}")
        return f"Error: Page loading timed out for {url}. This might be due to network issues or the page taking too long to load."
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Playwright error for {url}: {error_msg}")
        
        # 特殊处理常见错误
        if "net::ERR_ABORTED" in error_msg:
            if url.endswith('.pdf'):
                return f"Error: Cannot access PDF directly at {url}. PDF files may require special handling or may be blocked by the server."
            else:
                return f"Error: Access to {url} was aborted. This may be due to server restrictions, proxy issues, or anti-bot measures."
        elif "net::ERR_FAILED" in error_msg:
            return f"Error: Failed to connect to {url}. The server may be down or unreachable."
        elif "net::ERR_TIMED_OUT" in error_msg:
            return f"Error: Connection to {url} timed out. Please try again later."
        else:
            return f"Error: Unable to access {url}. Reason: {error_msg}"
    finally:
        await context.close()  # 关闭上下文会自动关闭其中的所有页面

def process_soup_content(soup, url: str, include_images: bool, include_links: bool, max_length: int) -> PageContent:
    """处理BeautifulSoup解析后的内容"""
    # 移除不需要的元素
    for tag in soup(['script', 'style', 'nav', 'footer', 'iframe', 'noscript']):
        tag.decompose()
    
    # 提取标题
    title = soup.title.string.strip() if soup.title else None
    
    # 提取元数据
    meta_info = {
        'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
        'keywords': soup.find('meta', {'name': 'keywords'})['content'] if soup.find('meta', {'name': 'keywords'}) else None,
        'author': soup.find('meta', {'name': 'author'})['content'] if soup.find('meta', {'name': 'author'}) else None,
        'language': soup.find('html', {'lang': True})['lang'] if soup.find('html', {'lang': True}) else None,
        'charset': soup.find('meta', {'charset': True})['charset'] if soup.find('meta', {'charset': True}) else None,
    }
            
    
    # 提取主要内容
    content = ""
    
    # 尝试查找主要内容区域
    main_selectors = [
        'main', 'article', '[role="main"]',
        '.content', '.main-content', '.article-content',
        '.post-content', '.entry-content', '#content'
    ]
    
    for selector in main_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            content = main_content.get_text(separator=' ', strip=True)
            break
    
    # 如果没找到主要内容，提取body内容
    if not content:
        body = soup.find('body')
        if body:
            content = body.get_text(separator=' ', strip=True)
    
    # 清理和限制内容长度
    clean_text = ' '.join(content.split())
    if len(clean_text) > max_length:
        clean_text = clean_text[:max_length] + '...'
    
    # 提取图片（如果需要）
    images = []
    if include_images:
        for img in soup.find_all('img', src=True):
            src = img['src']
            if not src.startswith(('http://', 'https://')):
                src = urljoin(url, src)
            images.append({
                'src': src,
                'alt': img.get('alt', ''),
                'title': img.get('title', '')
            })
    
    # 提取链接（如果需要）
    links = []
    if include_links:
        for link in soup.find_all('a', href=True):
            href = link['href']
            if not href.startswith(('http://', 'https://')):
                href = urljoin(url, href)
            links.append({
                'href': href,
                'text': link.get_text(strip=True),
                'title': link.get('title', '')
            })
    
    return PageContent(
        url=url,
        title=title,
        content=content[:max_length] if content else None,
        clean_text=clean_text,
        meta_info=meta_info,
        images=images[:20] if images else None,  # 限制图片数量
        links=links[:50] if links else None,    # 限制链接数量
        extraction_status='success',
        timestamp=format_timestamp()
    )

async def extract_pdf_content(url: str, max_length: int = 10000) -> PageContent:
    """尝试提取PDF内容的多种方法"""
    logger.info(f"Attempting to extract PDF content from: {url}")
    
    # 方法1: 尝试通过requests直接下载
    try:
        proxy_config = NETWORK_CONFIG.get("proxy", {})
        proxies = {}
        if proxy_config.get("http"):
            proxies["http"] = proxy_config["http"]
        if proxy_config.get("https"):
            proxies["https"] = proxy_config["https"]
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, proxies=proxies, timeout=30, stream=True)
        response.raise_for_status()
        
        # 检查是否真的是PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type and not url.endswith('.pdf'):
            logger.warning(f"URL {url} may not be a PDF file")
        
        # 尝试安装和使用PyPDF2来解析PDF
        try:
            import PyPDF2
            import io
            
            # 下载PDF内容
            pdf_content = response.content
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            
            text_content = ""
            for page_num in range(min(len(pdf_reader.pages), 10)):  # 限制前10页
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            # 清理和截断内容
            text_content = text_content.strip()
            if len(text_content) > max_length:
                text_content = text_content[:max_length] + "..."
            
            return PageContent(
                url=url,
                title=f"PDF Document: {url.split('/')[-1]}",
                content=text_content,
                extraction_status='success',
                timestamp=format_timestamp()
            )
            
        except ImportError:
            logger.warning("PyPDF2 not installed. Install with: pip install PyPDF2")
            return PageContent(
                url=url,
                extraction_status='error',
                error="PDF processing requires PyPDF2 library. Please install with: pip install PyPDF2",
                timestamp=format_timestamp()
            )
        except Exception as pdf_error:
            logger.error(f"PDF parsing error: {pdf_error}")
            return PageContent(
                url=url,
                title=f"PDF Document: {url.split('/')[-1]}",
                content=f"PDF file detected but content extraction failed. File size: {len(response.content)} bytes",
                extraction_status='partial',
                error=f"PDF parsing failed: {str(pdf_error)}",
                timestamp=format_timestamp()
            )
            
    except Exception as e:
        logger.error(f"Failed to download/process PDF from {url}: {e}")
        return PageContent(
            url=url,
            extraction_status='error',
            error=f"Failed to access PDF: {str(e)}",
            timestamp=format_timestamp()
        )

async def extract_clean_content(browser, url: str, include_images: bool = False, include_links: bool = False, max_length: int = 10000) -> PageContent:
    """提取网页的干净内容"""
    logger.debug(f"Starting content extraction for URL: {url}")
    
    # 检查是否是PDF文件
    if url.endswith('.pdf') or 'pdf' in url.lower():
        logger.info(f"Detected PDF URL: {url}, using PDF extraction method")
        return await extract_pdf_content(url, max_length)
    
    if not url or not url.startswith(('http://', 'https://')):
        return PageContent(
            url=url,
            extraction_status='error',
            error='Invalid URL format',
            timestamp=format_timestamp()
        )
    
    try:
        # 直接使用 Playwright 进行内容提取
        result = await extract_content_with_playwright(browser, url, include_images, include_links, max_length)
        
        # 检查是否返回错误信息
        if isinstance(result, str) and result.startswith("Error:"):
            return PageContent(
                url=url,
                extraction_status='error',
                error=result,
                timestamp=format_timestamp()
            )
        else:
            return result
            
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        logger.error(traceback.format_exc())
        return PageContent(
            url=url,
            extraction_status='error',
            error=str(e),
            timestamp=format_timestamp()
        )

async def capture_screenshot(browser, url: str, width: int = 1280, height: int = 720, full_page: bool = False, format: str = "png") -> ScreenshotResponse:
    """使用Playwright捕获网页截图"""
    logger.debug(f"Screenshot request for URL: {url}")
    
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": height})
    
    try:
        await page.goto(url, timeout=NETWORK_CONFIG["timeout"].get("read", 60) * 1000)
        
        screenshot_bytes = await page.screenshot(
            path=None, 
            full_page=full_page,
            type=format if format in ['png', 'jpeg'] else 'png'
        )
        
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        return ScreenshotResponse(
            url=url,
            screenshot_base64=screenshot_base64,
            width=width,
            height=height,
            format=format,
            timestamp=format_timestamp()
        )
    except Exception as e:
        logger.error(f"Error capturing screenshot for {url}: {str(e)}")
        return ScreenshotResponse(
            url=url,
            error=str(e),
            width=width,
            height=height,
            format=format,
            timestamp=format_timestamp()
        )
    finally:
        await context.close()

async def analyze_page_datetime(browser, url: str) -> DatetimeInfo:
    """分析网页的发布/更新时间"""
    logger.debug(f"Analyzing datetime for URL: {url}")
    
    try:
        # 使用 Playwright 获取页面内容进行分析
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, timeout=NETWORK_CONFIG["timeout"].get("read", 60) * 1000)
        html_content = await page.content()
        await context.close()

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找各种时间标记
        published_date = None
        updated_date = None
        detected_dates = []
        
        # 查找元数据中的时间
        date_metas = [
            'article:published_time', 'article:modified_time',
            'datePublished', 'dateModified', 'pubdate'
        ]
        
        for meta_name in date_metas:
            meta = soup.find('meta', {'property': meta_name}) or soup.find('meta', {'name': meta_name})
            if meta and meta.get('content'):
                date_str = meta['content']
                detected_dates.append(date_str)
                if 'published' in meta_name.lower() and not published_date:
                    published_date = date_str
                elif 'modified' in meta_name.lower() and not updated_date:
                    updated_date = date_str
        
        # 查找time标签
        for time_tag in soup.find_all('time'):
            datetime_attr = time_tag.get('datetime')
            if datetime_attr:
                detected_dates.append(datetime_attr)
                if not published_date:
                    published_date = datetime_attr
        
        # 简单的置信度计算
        confidence = min(1.0, len(detected_dates) * 0.3)
        
        return DatetimeInfo(
            url=url,
            published_date=published_date,
            updated_date=updated_date,
            detected_dates=detected_dates,
            confidence=confidence,
            method='meta_and_time_tags'
        )
                
    except Exception as e:
        logger.error(f"Error analyzing datetime for {url}: {str(e)}")
        return DatetimeInfo(
            url=url,
            error=str(e)
        )

# API 端点

@app.get("/test", 
         response_class=HTMLResponse,
         summary="测试页面",
         description="提供一个交互式的测试界面，可以直接在浏览器中测试所有 API 功能",
         tags=["测试工具"])
async def test_page():
    """返回测试页面"""
    try:
        with open("test.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>测试页面不存在</h1>
                <p>请确保 test.html 文件在当前目录中</p>
                <p><a href="/docs">点击这里访问 API 文档</a></p>
            </body>
        </html>
        """)

@app.get("/",
         response_class=HTMLResponse,
         summary="服务首页",
         description="Visit API 服务的欢迎页面，提供服务概览和快速链接",
         tags=["系统"])
async def root():
    """根端点 - 服务信息"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Visit API - 网页访问服务</title>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 50px 20px;
                color: white;
                text-align: center;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255,255,255,0.1);
                padding: 50px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            h1 {
                font-size: 3em;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .subtitle {
                font-size: 1.3em;
                margin-bottom: 40px;
                opacity: 0.9;
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 40px 0;
            }
            .feature {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .links {
                margin-top: 40px;
            }
            .btn {
                display: inline-block;
                background: rgba(255,255,255,0.2);
                color: white;
                padding: 15px 30px;
                margin: 10px;
                border-radius: 50px;
                text-decoration: none;
                border: 2px solid rgba(255,255,255,0.3);
                transition: all 0.3s;
                font-weight: 500;
            }
            .btn:hover {
                background: rgba(255,255,255,0.3);
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            }
            .status {
                background: rgba(76, 175, 80, 0.2);
                padding: 10px 20px;
                border-radius: 20px;
                display: inline-block;
                margin-bottom: 20px;
                border: 1px solid rgba(76, 175, 80, 0.5);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">🟢 服务运行中</div>
            <h1>🌐 Visit API</h1>
            <p class="subtitle">网页访问服务 - 内容提取、分析和处理</p>
            
            <div class="features">
                <div class="feature">
                    <h3>🔍 内容提取</h3>
                    <p>智能提取网页核心内容</p>
                </div>
                <div class="feature">
                    <h3>⚡ 并行处理</h3>
                    <p>同时处理多个网页</p>
                </div>
                <div class="feature">
                    <h3>🕒 时间分析</h3>
                    <p>分析网页时间信息</p>
                </div>
                <div class="feature">
                    <h3>📊 数据结构化</h3>
                    <p>返回结构化的数据</p>
                </div>
            </div>
            
            <div class="links">
                <a href="/test" class="btn">🧪 交互式测试</a>
                <a href="/docs" class="btn">📖 API 文档</a>
                <a href="/health" class="btn">💊 健康检查</a>
                <a href="/primer" class="btn">ℹ️ 系统信息</a>
            </div>
            
            <p style="margin-top: 40px; opacity: 0.7;">
                Visit API v1.0.0 | 基于 Jina MCP 接口设计
            </p>
        </div>
    </body>
    </html>
    """)

@app.post("/read_url", 
          response_model=ApiResponse,
          summary="提取网页内容",
          description="""
          提取指定网页的干净内容，包括标题、正文、元数据等信息。
          
          **支持的功能：**
          - 自动识别主要内容区域
          - 清理无用的标签和脚本
          - 提取图片和链接（可选）
          - 支持多种字符编码
          - 处理各种网站类型
          
          **示例网站：**
          - https://en.wikipedia.org/wiki/Artificial_intelligence
          - https://www.zhihu.com/question/xxxxx
          - https://news.ycombinator.com/item?id=xxxxx
          """,
          tags=["内容提取"])
async def read_url(request: ReadUrlRequest, http_request: Request):
    """提取网页内容"""
    logger.info(f"Reading URL: {request.url}")
    
    try:
        browser = http_request.app.state.browser
        content = await extract_clean_content(
            browser=browser,
            url=request.url,
            include_images=request.include_images,
            include_links=request.include_links,
            max_length=request.max_content_length
        )
        
        return ApiResponse(
            code=200,
            log_id=datetime.now().strftime('%Y%m%d%H%M%S'),
            msg="Success",
            data=content.model_dump(),
            timestamp=format_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Error reading URL {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parallel_read", 
          response_model=ApiResponse,
          summary="并行读取多个网页",
          description="""
          同时读取多个网页的内容，适用于需要快速获取多个页面信息的场景。
          
          **特点：**
          - 并发处理，显著提高效率
          - 自动处理失败的请求
          - 支持最多同时处理 10 个网页
          - 返回所有结果（包括失败的）
          
          **使用场景：**
          - 新闻聚合
          - 内容比较
          - 批量数据收集
          """,
          tags=["内容提取"])
async def parallel_read(request: ParallelReadRequest, http_request: Request):
    """并行读取多个网页"""
    logger.info(f"Parallel reading {len(request.urls)} URLs")
    
    try:
        # 限制最大并发数
        max_parallel = CONTENT_CONFIG["parallel_limit"]
        if len(request.urls) > max_parallel:
            raise HTTPException(
                status_code=400, 
                detail=f"最多支持同时读取 {max_parallel} 个网页"
            )
        
        browser = http_request.app.state.browser
        # 创建并发任务
        tasks = []
        for url in request.urls:
            task = extract_clean_content(
                browser=browser,
                url=url,
                include_images=request.include_images,
                include_links=request.include_links,
                max_length=request.max_content_length
            )
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "url": request.urls[i],
                    "extraction_status": "error",
                    "error": str(result),
                    "timestamp": format_timestamp()
                })
            else:
                processed_results.append(result.model_dump())
        
        return ApiResponse(
            code=200,
            log_id=datetime.now().strftime('%Y%m%d%H%M%S'),
            msg="Parallel read completed",
            data=processed_results,
            timestamp=format_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Error in parallel read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/screenshot", 
          response_model=ApiResponse,
          summary="网页截图",
          description="""
          捕获网页的截图图像。
          
          **注意：** 当前为模拟实现，实际部署需要集成浏览器引擎（如 Playwright 或 Selenium）。
          
          **参数说明：**
          - width/height: 截图尺寸
          - full_page: 是否截取整个页面
          - format: 图片格式 (png/jpeg)
          
          **实际实现需要：**
          ```bash
          pip install playwright
          playwright install chromium
          ```
          """,
          tags=["图像处理"])
async def screenshot(request: ScreenshotRequest, http_request: Request):
    """网页截图（模拟实现）"""
    logger.info(f"Screenshot request for: {request.url}")
    
    try:
        browser = http_request.app.state.browser
        screenshot_result = await capture_screenshot(
            browser=browser,
            url=request.url,
            width=request.width,
            height=request.height,
            full_page=request.full_page,
            format=request.format
        )
        
        return ApiResponse(
            code=200,
            log_id=datetime.now().strftime('%Y%m%d%H%M%S'),
            msg="Screenshot completed (mock)",
            data=screenshot_result.model_dump(),
            timestamp=format_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze_datetime", 
          response_model=ApiResponse,
          summary="分析网页时间信息",
          description="""
          分析网页的发布时间和更新时间。
          
          **分析方法：**
          - 提取 HTML meta 标签中的时间信息
          - 查找 `<time>` 标签的 datetime 属性
          - 检测常见的时间格式
          - 计算检测置信度
          
          **适用网站：**
          - 新闻网站
          - 博客文章
          - 技术文档
          - 社交媒体帖子
          """,
          tags=["数据分析"])
async def analyze_datetime(request: DatetimeAnalysisRequest, http_request: Request):
    """分析网页的发布/更新时间"""
    logger.info(f"Analyzing datetime for: {request.url}")
    
    try:
        browser = http_request.app.state.browser
        datetime_info = await analyze_page_datetime(browser, request.url)
        
        return ApiResponse(
            code=200,
            log_id=datetime.now().strftime('%Y%m%d%H%M%S'),
            msg="Datetime analysis completed",
            data=datetime_info.model_dump(),
            timestamp=format_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Error analyzing datetime: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", 
          response_model=ApiResponse,
          summary="网络搜索",
          description="""
          执行网络搜索并返回结果。
          
          **注意：** 当前为模拟实现，实际部署需要集成搜索引擎 API。
          
          **可集成的搜索引擎：**
          - DuckDuckGo (免费)
          - Google Custom Search API
          - Bing Search API
          - SerpAPI
          
          **实际实现需要：**
          ```bash
          pip install duckduckgo-search playwright
          playwright install
          ```
          """,
          tags=["搜索"])
async def search_web(request: SearchRequest):
    """网络搜索（模拟实现）"""
    logger.info(f"Search request for: {request.query}")
    
    # 这是一个模拟实现，实际需要集成搜索引擎API
    mock_results = [
        {
            "title": f"搜索结果 1: {request.query}",
            "url": "https://example.com/search-result-1",
            "snippet": f"这是关于 '{request.query}' 的第一个搜索结果摘要...",
            "rank": 1
        },
        {
            "title": f"搜索结果 2: {request.query}",
            "url": "https://example.com/search-result-2", 
            "snippet": f"这是关于 '{request.query}' 的第二个搜索结果摘要...",
            "rank": 2
        }
    ]
    
    return ApiResponse(
        code=200,
        log_id=datetime.now().strftime('%Y%m%d%H%M%S'),
        msg="Search completed (mock)",
        data={
            "query": request.query,
            "results": mock_results[:request.max_results],
            "total_results": len(mock_results),
            "language": request.language
        },
        timestamp=format_timestamp()
    )

@app.get("/health",
         summary="健康检查",
         description="检查服务的运行状态和系统健康状况",
         tags=["系统"])
async def health_check():
    """健康检查"""
    logger.info("Health check endpoint accessed")
    
    # 检查代理状态
    proxy_config = NETWORK_CONFIG.get("proxy", {})
    proxy_enabled = proxy_config.get("enabled", False)
    proxy_url = None
    if proxy_enabled:
        proxy_url = proxy_config.get("https") or proxy_config.get("http")
    
    health_status = {
        "status": "healthy",
        "service": "Visit API",
        "version": "1.0.0",
        "timestamp": format_timestamp(),
        "proxy_enabled": proxy_enabled,
        "proxy_url": proxy_url if proxy_enabled else None,
        "checks": {
            "logging": "ok",
            "memory": "ok",
            "disk_space": "ok",
            "proxy": "enabled" if proxy_enabled else "disabled"
        }
    }
    
    return health_status

@app.get("/primer",
         summary="系统信息",
         description="""
         提供系统上下文信息，包括时间戳、网络信息、服务能力等。
         
         **返回信息：**
         - 当前时间戳和时区
         - 系统主机名和IP
         - 平台和Python版本
         - 服务版本和能力列表
         """,
         tags=["系统"])
async def primer():
    """提供系统上下文信息"""
    import socket
    import platform
    
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        hostname = "unknown"
        local_ip = "unknown"
    
    return {
        "timestamp": format_timestamp(),
        "timezone": str(pytz.UTC),
        "system_info": {
            "hostname": hostname,
            "local_ip": local_ip,
            "platform": platform.system(),
            "python_version": platform.python_version()
        },
        "client_context": {
            "service": "Visit API",
            "version": "1.0.0",
            "capabilities": [
                "read_url", "parallel_read", "screenshot", 
                "analyze_datetime", "search", "health_check"
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Visit API server...")
    logger.info(f"Log file: {log_filename}")
    
    uvicorn.run(
        "app:app",
        host=SERVICE_CONFIG.get("host", "0.0.0.0"),
        port=SERVICE_CONFIG.get("port", 8002),
        log_level="info",
        reload=False # reload=True might cause issues with the asyncio policy
    )
