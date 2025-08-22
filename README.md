# Visit API - Page Access Service

基于 Jina AI MCP 接口设计的页面访问服务，提供网页内容提取、分析和处理功能。

## 功能特性

### 核心功能
- **read_url**: 提取网页的干净内容
- **parallel_read**: 并行读取多个网页
- **screenshot**: 网页截图（需要浏览器引擎）
- **analyze_datetime**: 分析网页发布/更新时间
- **search**: 网络搜索功能
- **primer**: 系统上下文信息

### 特点
- 异步处理，支持高并发
- 智能内容提取和清理
- 元数据分析
- 图片和链接提取
- 完整的错误处理和日志记录
- CORS 支持
- RESTful API 设计

## 安装和运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务
```bash
python app.py
```

服务将在 `http://localhost:8001` 启动

### 3. 使用 uvicorn 启动（推荐）
```bash
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

## API 端点

### 1. 读取网页内容
```http
POST /read_url
Content-Type: application/json

{
    "url": "https://example.com",
    "include_images": true,
    "include_links": true,
    "max_content_length": 10000
}
```

### 2. 并行读取多个网页
```http
POST /parallel_read
Content-Type: application/json

{
    "urls": [
        "https://example1.com",
        "https://example2.com"
    ],
    "include_images": false,
    "include_links": true,
    "max_content_length": 5000
}
```

### 3. 网页截图（模拟）
```http
POST /screenshot
Content-Type: application/json

{
    "url": "https://example.com",
    "width": 1280,
    "height": 720,
    "full_page": false,
    "format": "png"
}
```

### 4. 分析网页时间信息
```http
POST /analyze_datetime
Content-Type: application/json

{
    "url": "https://news.example.com/article"
}
```

### 5. 网络搜索（模拟）
```http
POST /search
Content-Type: application/json

{
    "query": "AI technology",
    "max_results": 10,
    "language": "en"
}
```

### 6. 健康检查
```http
GET /health
```

### 7. 系统信息
```http
GET /primer
```

## 响应格式

所有 API 响应都遵循统一格式：

```json
{
    "code": 200,
    "log_id": "20250822145230",
    "msg": "Success",
    "data": {
        // 具体数据内容
    },
    "timestamp": "2025-08-22T14:52:30+00:00"
}
```

## 配置说明

### 日志配置
- 自动生成带时间戳的日志文件
- 同时输出到控制台和文件
- 支持调试级别日志

### 网络配置
- 30秒请求超时
- 10秒连接超时
- 自动重试机制
- 支持重定向

### 内容提取
- 智能识别主要内容区域
- 自动清理无用标签
- 支持多种编码格式
- 内容长度限制

## 扩展功能

### 截图功能实现
要实现真正的截图功能，需要集成浏览器引擎：

```python
# 使用 Playwright 的示例
from playwright.async_api import async_playwright

async def real_screenshot(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        screenshot = await page.screenshot()
        await browser.close()
        return base64.b64encode(screenshot).decode()
```

### 搜索功能实现
集成真实搜索引擎 API：

```python
# 集成 DuckDuckGo 或其他搜索引擎
from duckduckgo_search import DDGS

async def real_search(query: str):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=10))
        return results
```

## 开发和测试

### 测试端点
```bash
# 测试健康检查
curl http://localhost:8001/health

# 测试读取网页
curl -X POST http://localhost:8001/read_url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://httpbin.org/html"}'
```

### 日志查看
日志文件会自动生成在当前目录，格式为 `visitapi_YYYYMMDD_HHMMSS.log`

## 与 Jina MCP 的对应关系

| Jina MCP 工具 | Visit API 端点 | 说明 |
|---------------|----------------|------|
| read_url | /read_url | 提取网页内容 |
| parallel_read_url | /parallel_read | 并行读取多个网页 |
| capture_screenshot_url | /screenshot | 网页截图 |
| guess_datetime_url | /analyze_datetime | 分析网页时间 |
| search_web | /search | 网络搜索 |
| primer | /primer | 系统上下文 |

## 注意事项

1. **截图功能**: 当前为模拟实现，需要浏览器引擎支持
2. **搜索功能**: 当前为模拟实现，需要集成搜索引擎 API
3. **网络访问**: 部分网站可能有反爬虫机制
4. **内容编码**: 自动处理多种字符编码
5. **错误处理**: 完整的异常捕获和错误响应

## 许可证

MIT License
