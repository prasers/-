"""
pages/p3_diagnosis.py · v5 重构
P3 故障智能诊断

v5 优化点：
1. [视觉] 诊断结果用等级徽章（🔴错误/🟡警告/🟢正常）
2. [智能] 传统算法+Claude Vision 双层诊断融合
3. [交互] 上传即预览，诊断中进度条动效
4. [体验] 分步调试方案可折叠/展开
5. [容错] Vision API 失败自动退回传统算法
6. [场景] 5类常见故障全覆盖 + 分步解决方案
"""

import streamlit as st
import cv2
import numpy as np
import base64
import json
from datetime import datetime

try:
    import anthropic
    ANTHROPIC_OK = True
except ImportError:
    ANTHROPIC_OK = False

FAULT_RULES = {
    "elliptical": {
        "name": "干涉环椭圆/不圆", "level": "warning",
        "component": "反射镜 M1/M2、分光板",
        "steps": [
            "检查 M1、M2 是否垂直于光路",
            "调节 M2 背部三个精调螺丝，使干涉环趋于圆形",
            "确认分光板与补偿板平行度",
            "重新对准光路，使各光束共轴"
        ]
    },
    "off_center": {
        "name": "干涉环中心偏移", "level": "warning",
        "component": "反射镜角度、光路遮挡",
        "steps": [
            "调节 M2 的倾斜角，使圆心移回视场中央",
            "检查光路中是否有遮挡物",
            "确认扩束镜是否偏离光轴",
            "严重偏移时重新进行光路粗准直"
        ]
    },
    "blurry": {
        "name": "干涉环模糊/对比度低", "level": "warning",
        "component": "扩束镜、聚焦、振动",
        "steps": [
            "调整扩束镜前后位置，优化准直光束质量",
            "检查激光器输出功率是否正常",
            "隔离振动源：关闭空调、使用减振台",
            "清洁各光学元件表面（擦镜纸轻拂）"
        ]
    },
    "not_moving": {
        "name": "干涉环不移动/移动不均", "level": "error",
        "component": "微调手轮空程、金属丝拉伸装置",
        "steps": [
            "消除空程：先向一个方向旋转至少5圈后再测量",
            "检查金属丝拉伸夹具是否松动，重新紧固",
            "确认 M1 镜架与调节机构连接紧固",
            "加砝码后等待约10秒让金属丝稳定"
        ]
    },
    "no_fringes": {
        "name": "无干涉条纹", "level": "error",
        "component": "光路、反射镜角度、光源",
        "steps": [
            "检查 He-Ne 激光器是否正常点亮",
            "用白纸逐段检查光路，确认各镜面有反射光",
            "重新粗准直：调节 M2 使两束光斑重合",
            "确认分光板插入方向和镀膜面正确"
        ]
    }
}


def _init():
    defs = {"p3_logs": [], "p3_last_result": None}
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _trad_diagnose(img_bgr) -> dict:
    """传统算法快速诊断"""
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 1. 模糊/无条纹
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap < 15:
            return {"fault": "no_fringes", "confidence": 0.85,
                    "detail": f"拉普拉斯方差={lap:.1f}，对比度极低"}
        if lap < 40:
            return {"fault": "blurry", "confidence": 0.75,
                    "detail": f"拉普拉斯方差={lap:.1f}，条纹模糊"}

        # 2. 中心ROI
        cx, cy = w//2, h//2
        r = min(w, h) // 4
        roi = gray[max(0,cy-r):cy+r, max(0,cx-r):cx+r]
        _, thr = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cnts, _ = cv2.findContours(thr, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # 3. 椭圆度检测
        ell_cnt = 0
        for cnt in cnts:
            if len(cnt) >= 5 and cv2.contourArea(cnt) > 80:
                try:
                    (_, _), (ma, mi), _ = cv2.fitEllipse(cnt)
                    if mi > 0 and (ma / mi) > 1.4:
                        ell_cnt += 1
                except Exception:
                    pass
        if ell_cnt >= 3:
            return {"fault": "elliptical", "confidence": 0.80,
                    "detail": f"检测到 {ell_cnt} 个椭圆轮廓"}

        # 4. 中心偏移
        top, bot = gray[:h//2].mean(), gray[h//2:].mean()
        lft, rgt = gray[:, :w//2].mean(), gray[:, w//2:].mean()
        if abs(top - bot) > 45 or abs(lft - rgt) > 45:
            return {"fault": "off_center", "confidence": 0.70,
                    "detail": f"亮度不对称（上下差={abs(top-bot):.1f}，左右差={abs(lft-rgt):.1f}）"}

        return {"fault": "normal", "confidence": 0.80,
                "detail": f"拉普拉斯方差={lap:.1f}，未检测到明显故障"}
    except Exception as e:
        return {"fault": "unknown", "confidence": 0.0, "detail": str(e)}


def _vision_diagnose(img_bgr, hint: str = "") -> dict | None:
    """Claude Vision API 增强诊断"""
    if not ANTHROPIC_OK:
        return None
    try:
        from modules.config import ANTHROPIC_API_KEY
        _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buf.tobytes()).decode()
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=600,
            system="""你是迈克尔逊干涉仪专家。分析干涉条纹图像，严格只返回JSON，格式：
{"fault":"elliptical"|"off_center"|"blurry"|"not_moving"|"no_fringes"|"normal",
 "confidence":0.0~1.0,"detail":"简短描述","suggestion":"1句话调试建议"}""",
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": f"分析此干涉条纹图像的故障情况。{hint}"}
            ]}]
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return None


def _render_result(trad: dict, vision: dict | None):
    """渲染诊断结果（传统+Vision融合）"""
    # 决策：Vision 有结果且置信度更高则采用
    if vision and vision.get("confidence", 0) > trad.get("confidence", 0):
        primary = vision
        src = "🤖 Claude Vision"
    else:
        primary = trad
        src = "⚙ 传统算法"

    fault_key = primary.get("fault", "unknown")
    conf = primary.get("confidence", 0)
    detail = primary.get("detail", "")
    suggestion = primary.get("suggestion", "")

    if fault_key == "normal":
        st.markdown(f'<div class="ok-bar">🟢 <b>未检测到明显故障</b> · 置信度 {conf:.0%} · {src}<br><small>{detail}</small></div>',
                    unsafe_allow_html=True)
        return

    rule = FAULT_RULES.get(fault_key, {
        "name": "未知故障", "level": "error",
        "component": "需人工排查", "steps": ["请检查仪器状态并联系实验指导老师"]
    })
    level = rule["level"]
    icon = "🔴" if level == "error" else "🟡"
    css = "err-bar" if level == "error" else "warn-bar"
    label = "错误" if level == "error" else "警告"

    st.markdown(f"""<div class="{css}">
    {icon} <b>[{label}] {rule['name']}</b> · 置信度 {conf:.0%} · {src}<br>
    <small>📍 相关部件：{rule['component']}</small><br>
    <small>🔍 算法分析：{detail}</small>
    {f'<br><small>💡 {suggestion}</small>' if suggestion else ''}
    </div>""", unsafe_allow_html=True)

    with st.expander("🛠 分步调试方案", expanded=True):
        for i, step in enumerate(rule["steps"], 1):
            st.markdown(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px">
              <div style="background:#003893;color:white;width:24px;height:24px;border-radius:50%;
                   flex-shrink:0;display:flex;align-items:center;justify-content:center;
                   font-size:12px;font-weight:700;margin-top:1px">{i}</div>
              <div style="font-size:14px;line-height:1.6;color:#0A1628">{step}</div>
            </div>""", unsafe_allow_html=True)

    # Vision 额外细节
    if vision and vision != primary:
        with st.expander("🤖 Claude Vision 补充分析"):
            st.caption(f"Vision 判断：{FAULT_RULES.get(vision.get('fault',''),{}).get('name', vision.get('fault',''))} · 置信度 {vision.get('confidence',0):.0%}")
            if vision.get("detail"):
                st.caption(f"分析：{vision.get('detail')}")

    # 记录日志
    log = {
        "时间": datetime.now().strftime("%H:%M:%S"),
        "故障": rule["name"],
        "等级": label,
        "来源": src,
        "置信度": f"{conf:.0%}"
    }
    if log not in st.session_state.p3_logs:
        st.session_state.p3_logs.append(log)


def render_p3():
    _init()
    st.markdown("""<div class="card">
    <div class="card-title" style="font-size:18px">🔧 实验故障智能诊断系统
      <span style="font-size:12px;font-weight:400;color:#4A6080;margin-left:10px">P3 · 传统算法 + Claude Vision 双层诊断</span>
    </div>
    <div style="font-size:13px;color:#4A6080;line-height:1.9">
      上传干涉条纹图片 → 系统自动识别故障类型 → 给出分步调试方案<br>
      支持：干涉环椭圆、中心偏移、条纹模糊、不移动、无条纹 5 类故障
    </div></div>""", unsafe_allow_html=True)

    t1, t2 = st.tabs(["🖼 图片上传诊断", "📋 诊断日志"])

    with t1:
        st.markdown('<div class="info-bar">💡 建议上传清晰的干涉条纹截图，分辨率越高诊断越准确。支持 JPG、PNG 格式。</div>',
                    unsafe_allow_html=True)
        col_up, col_res = st.columns([1, 1.2], gap="large")

        with col_up:
            uploaded = st.file_uploader("上传干涉条纹图片", type=["jpg","jpeg","png"],
                                         label_visibility="collapsed")
            if uploaded:
                raw = np.frombuffer(uploaded.read(), np.uint8)
                img_bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                if img_bgr is not None:
                    st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB),
                             caption="上传的干涉条纹图像", width="stretch")
                    # 图像基本信息
                    h, w = img_bgr.shape[:2]
                    lap = cv2.Laplacian(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                    c1, c2 = st.columns(2)
                    c1.metric("图像尺寸", f"{w}×{h}")
                    c2.metric("清晰度分数", f"{lap:.0f}")
                    if lap < 40:
                        st.markdown('<div class="warn-bar">⚠ 图像清晰度较低，建议重新拍摄以提高诊断准确率</div>',
                                    unsafe_allow_html=True)
                    hint = st.text_input("补充说明（可选）", placeholder="如：最近干涉环不移动，手轮已调整",
                                         help="告诉系统你观察到的现象，有助于提高诊断准确率")
                    btn = st.button("🔍 开始诊断", type="primary", use_container_width=True)

                    if btn:
                        with col_res:
                            with st.spinner("正在诊断…"):
                                trad = _trad_diagnose(img_bgr)
                                vision = _vision_diagnose(img_bgr, hint)
                            _render_result(trad, vision)
                else:
                    st.error("❌ 图片解码失败，请重新上传")
            else:
                st.markdown("""<div style="border:2px dashed #D0DDF5;border-radius:12px;padding:40px;
                    text-align:center;color:#4A6080;margin:16px 0">
                    <div style="font-size:48px;margin-bottom:12px">🖼</div>
                    <div style="font-size:16px;font-weight:600">上传干涉条纹图片</div>
                    <div style="font-size:13px;margin-top:8px;opacity:0.7">支持 JPG · PNG</div>
                    </div>""", unsafe_allow_html=True)

        if not uploaded:
            with col_res:
                st.markdown("""<div style="text-align:center;padding:60px 20px;color:#4A6080">
                <div style="font-size:52px;margin-bottom:16px">🔧</div>
                <div style="font-size:15px">上传图片后点击「开始诊断」<br>系统自动识别故障类型</div>
                </div>""", unsafe_allow_html=True)

    with t2:
        if not st.session_state.p3_logs:
            st.markdown('<div class="info-bar">暂无诊断记录，完成首次诊断后将在此显示历史记录</div>',
                        unsafe_allow_html=True)
        else:
            import pandas as pd
            df = pd.DataFrame(st.session_state.p3_logs)
            st.dataframe(df, use_container_width=True)
            if st.button("🗑 清空日志"):
                st.session_state.p3_logs = []
                st.rerun()
            csv = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("⬇ 导出诊断日志", csv, "diagnosis_log.csv", "text/csv")
