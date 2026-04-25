# 迈克尔逊干涉法测金属杨氏模量一体化实验系统
**深圳技术大学 大学物理实验竞赛参赛项目 · v4.0**

## 功能模块

| 模块 | 功能 |
|------|------|
| P0 · 干涉环计数 | 传统算法+CNN自动统计 ΔN，实时画面显示 |
| P1 · 数据计算分析 | 一键计算杨氏模量 E，完整不确定度分析，PDF报告导出 |
| P2 · 创创智能体 | 卡通语音问答，中英双语，自定义知识库 |
| P3 · 故障诊断 | Claude Vision API 自动识别干涉条纹异常 |

## 快速启动（本地）

```bash
pip install -r requirements.txt
streamlit run app.py
```

> **API Key 已内置**，无需任何额外配置，直接运行即可。

## 公网一键启动（Windows）

### 方式 1：已有公网域名 / 反向代理地址

```powershell
.\start_public.ps1 -PublicBaseUrl "https://your-domain.example.com"
```

- 不传 `-PublicBaseUrl` 也能启动，但二维码默认显示局域网地址。
- 如果你已在系统环境变量里配置 `PUBLIC_BASE_URL`，可直接运行：

```powershell
.\start_public.ps1
```

### 方式 2：临时公网地址（cloudflared）

```powershell
.\start_public_cloudflared.ps1
```

- cloudflared 会输出 `https://xxxxx.trycloudflare.com` 临时公网链接。
- 把这个链接复制出来后，可再用方式 1 启动并传给 `-PublicBaseUrl`，让页面二维码也显示公网地址。

## Vercel 一键部署

1. Fork 本仓库到 GitHub
2. 在 Vercel 导入项目
3. 直接部署（无需配置任何环境变量）

## 核心实验公式

E = 8Fl / (π d² λ ΔN)

其中：F 为拉力，l 为金属丝原长，d 为直径，λ 为激光波长，ΔN 为干涉环变化量

## 技术栈

- 前端：Streamlit · HTML5 Canvas · Web Speech API
- 后端：Python · OpenCV · NumPy · SciPy
- AI：Anthropic Claude API (Vision + 对话)
- 部署：Vercel

© 2025 深圳技术大学 大学物理实验竞赛
