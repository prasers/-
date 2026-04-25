# 迈克尔逊干涉法测金属杨氏模量一体化实验系统
**深圳技术大学 大学物理实验竞赛参赛项目 · v5.0**

## 功能模块

| 模块 | 功能 |
|------|------|
| P0 · 干涉环计数 | 传统算法+CNN 自动统计 ΔN，支持摄像头/视频/图片序列 |
| P1 · 数据计算分析 | 一键计算杨氏模量 E，完整不确定度分析，TXT/PDF 导出 |
| P2 · 创创智能体 | 卡通语音问答，中英双语，支持音色切换与知识库自定义 |
| P3 · 故障诊断 | 传统算法 + Vision 识别干涉条纹异常并给出调试建议 |

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud 部署

1. 将代码推送到 GitHub 仓库。
2. 在 Streamlit Community Cloud 新建应用并选择仓库。
3. `Main file path` 填写：
   - `sztu-v5-final/app.py`
4. 部署后若修改了依赖，执行一次 `Reboot app` 触发重建环境。

### 推荐 Secrets（在 App Settings -> Secrets 配置）

```toml
OPENAI_API_KEY = "your_openai_or_zhipu_key"
OPENAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
ANTHROPIC_API_KEY = "your_anthropic_key"
PUBLIC_BASE_URL = "https://your-streamlit-app-url.streamlit.app"
```

- `PUBLIC_BASE_URL` 用于顶部二维码显示公网访问地址（可选）。
- 若不配置，会自动显示局域网地址。

## 公网一键启动（Windows，本地演示用）

### 方式 1：已有公网域名 / 反向代理地址

```powershell
.\start_public.ps1 -PublicBaseUrl "https://your-domain.example.com"
```

### 方式 2：临时公网地址（cloudflared）

```powershell
.\start_public_cloudflared.ps1
```

## 常见问题排查

- 页面显示 `Oh no. Error running app`：
  - 先看 Streamlit Cloud 日志首条 Traceback。
  - 确认 `Main file path` 是 `sztu-v5-final/app.py`。
  - 确认 `requirements.txt` 已提交到同目录。
- 出现 API 调用失败：
  - 检查 Secrets 中对应的 Key 是否存在且有效。
- 页面出现前端渲染异常：
  - 先硬刷新浏览器并清缓存；
  - 再重启应用观察是否复现。

## 核心实验公式

E = 8Fl / (π d² λ ΔN)

其中：F 为拉力，l 为金属丝原长，d 为直径，λ 为激光波长，ΔN 为干涉环变化量。

## 技术栈

- 前端：Streamlit · HTML5 Canvas · Web Speech API
- 后端：Python · OpenCV · NumPy · SciPy
- AI：OpenAI SDK（兼容智谱 API）· Anthropic Vision
- 部署：Streamlit Community Cloud

© 2025 深圳技术大学 大学物理实验竞赛
