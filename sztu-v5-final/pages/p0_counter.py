"""
pages/p0_counter.py · v5 重构
P0 干涉环计数系统

v5 优化点：
1. [交互] 计数控制区用卡片包裹，视觉层级更清晰
2. [显示] ΔN 使用 big-display 令牌 + pos/neg 色彩反馈
3. [反馈] 每次触发闪烁动画 + 方向箭头动态显示
4. [容错] 输入验证、摄像头不可用时友好提示
5. [智能] 实时故障诊断集成，每5帧自动触发
6. [性能] R003 跳帧+多线程视频处理保留
7. [体验] 一键同步有成功动效，防止重复点击
"""

import streamlit as st
import cv2
import numpy as np
import tempfile, os
from datetime import datetime
import pandas as pd

try:
    from modules.ring_counter import RingCounter, ROIConfig, VideoProcessor
    COUNTER_OK = True
except ImportError as e:
    COUNTER_OK = False
    _import_err = str(e)


def _init():
    defs = {
        "p0_counter": RingCounter() if COUNTER_OK else None,
        "p0_history": [],
        "p0_status": "stopped",
        "p0_roi": 0.28,
        "p0_last_frame": None,
        "p0_diag_cnt": 0,
        "p0_diag_last": None,
        "p0_sync_ok": False,
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _dn_display(dn: int, status: str, last_dir: str = None):
    cls = "pos" if dn > 0 else ("neg" if dn < 0 else "")
    dir_icon = {"eject": "⬆ 吐出", "absorb": "⬇ 吞入"}.get(last_dir or "", "─ 无事件")
    pill_map = {
        "running": ('<span class="pill pill-run">计数中</span>', ""),
        "paused":  ('<span class="pill pill-pause">⏸ 已暂停</span>', ""),
        "stopped": ('<span class="pill pill-stop">■ 未启动</span>', ""),
    }
    pill_html, _ = pill_map.get(status, pill_map["stopped"])
    st.markdown(f"""
    <div class="big-display">
      <div class="big-label">累计变化量 ΔN</div>
      <div class="big-value {cls}">{dn:+d}</div>
      <div class="big-unit">环数 &nbsp;|&nbsp; 吐出 +1 · 吞入 −1</div>
      <div class="big-sub" style="display:flex;justify-content:center;gap:12px;margin-top:12px;flex-wrap:wrap">
        {pill_html}
        <span class="pill pill-info">{dir_icon}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _quick_fault_check(frame):
    """传统算法快速故障诊断（复用P0帧，R007）"""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap < 20:
            return {"level": "error", "fault": "条纹模糊 / 无干涉条纹",
                    "hint": "① 调整扩束镜焦距 ② 减少外界振动 ③ 检查激光是否开启"}
        cx, cy, r = w//2, h//2, min(w,h)//4
        roi = gray[max(0,cy-r):cy+r, max(0,cx-r):cx+r]
        _, thr = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        cnts, _ = cv2.findContours(thr, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        ell_cnt = sum(1 for c in cnts if len(c) >= 5 and cv2.contourArea(c) > 80
                      and _is_ellipse(c))
        if ell_cnt >= 3:
            return {"level": "warning", "fault": "干涉环呈椭圆形",
                    "hint": "① M1/M2镜不垂直，微调调整螺丝 ② 检查光路是否平行"}
        if abs(gray[:h//2].mean() - gray[h//2:].mean()) > 40:
            return {"level": "warning", "fault": "干涉环中心偏移",
                    "hint": "① 调整迈克尔逊干涉仪水平 ② 重新对准分束镜"}
        return None
    except Exception:
        return None


def _is_ellipse(cnt):
    try:
        (_, _), (ma, mi), _ = cv2.fitEllipse(cnt)
        return mi > 0 and (ma/mi) > 1.4
    except Exception:
        return False


def _cam_placeholder():
    sz = 380
    img = np.full((sz, sz, 3), (12, 8, 24), dtype=np.uint8)
    cx = cy = sz // 2
    for r in range(18, 170, 20):
        c = int(140 + 80 * np.sin(r / 7))
        cv2.circle(img, (cx, cy), r, (c//4, c//5, c), 7)
    cv2.circle(img, (cx, cy), 80, (0, 200, 216), 2)
    cv2.putText(img, "DEMO", (cx-30, cy+5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,200,216), 1)
    cv2.putText(img, "Click to capture", (cx-72, sz-16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120,140,180), 1)
    st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
             caption="示意图：对准干涉环中心后拍照", width="stretch")


def _render_camera_tab():
    st.markdown("""<div class="info-bar">
    📷 <b>摄像头模式</b>：点击拍照采集帧，系统分析干涉环变化量。<br>
    💡 建议将摄像头对准干涉环中心区域，调整 ROI 使识别框覆盖约 3~5 个环。
    </div>""", unsafe_allow_html=True)

    col_cam, col_ctrl = st.columns([1.4, 1], gap="large")

    with col_ctrl:
        st.markdown('<div class="card-title">⚙ 计数控制</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            start_dis = (st.session_state.p0_status == "running")
            if st.button("▶ 开始", use_container_width=True, type="primary", disabled=start_dis):
                st.session_state.p0_status = "running"
                if st.session_state.p0_counter:
                    st.session_state.p0_counter.start()
                st.rerun()
        with c2:
            pause_dis = (st.session_state.p0_status != "running")
            if st.button("⏸ 暂停", use_container_width=True, disabled=pause_dis):
                st.session_state.p0_status = "paused"
                if st.session_state.p0_counter:
                    st.session_state.p0_counter.pause()
                st.rerun()
        with c3:
            if st.button("⏹ 重置", use_container_width=True):
                st.session_state.p0_status = "stopped"
                st.session_state.p0_history = []
                st.session_state.delta_n = 0
                st.session_state.p0_diag_last = None
                if st.session_state.p0_counter:
                    st.session_state.p0_counter.reset()
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        last_dir = None
        if st.session_state.p0_counter:
            try: last_dir = st.session_state.p0_counter.state.last_direction
            except Exception: pass
        _dn_display(st.session_state.delta_n, st.session_state.p0_status, last_dir)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="card-title">✏ 手动补正</div>', unsafe_allow_html=True)
        st.caption("检测到漏计/误计时，可手动修正")
        adj1, adj2 = st.columns(2)
        with adj1:
            if st.button("＋1", use_container_width=True):
                st.session_state.delta_n += 1
                if st.session_state.p0_counter:
                    st.session_state.p0_counter.manual_adjust(1)
                st.rerun()
        with adj2:
            if st.button("－1", use_container_width=True):
                st.session_state.delta_n -= 1
                if st.session_state.p0_counter:
                    st.session_state.p0_counter.manual_adjust(-1)
                st.rerun()
        adj_val = st.number_input("精确补正", value=0, step=1, key="p0_adj",
                                   help="正数增加 ΔN，负数减少 ΔN")
        if st.button("应用补正", use_container_width=True):
            st.session_state.delta_n += int(adj_val)
            if st.session_state.p0_counter:
                st.session_state.p0_counter.manual_adjust(int(adj_val))
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 ROI 设置</div>', unsafe_allow_html=True)
        roi = st.slider("ROI 半径比例", 0.10, 0.50, st.session_state.p0_roi, 0.01,
                        help="ROI 圆形区域占画面短边的比例，建议 0.25~0.35")
        auto_c = st.checkbox("自动检测圆心", value=True)
        if roi != st.session_state.p0_roi:
            st.session_state.p0_roi = roi
            if st.session_state.p0_counter:
                st.session_state.p0_counter.roi_cfg.roi_ratio = roi
                st.session_state.p0_counter.roi_cfg.auto_detect = auto_c

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📤 一键同步 ΔN 到 P1 计算模块", use_container_width=True, type="primary"):
            st.session_state.p1_sync_delta_n = st.session_state.delta_n
            st.session_state.p0_sync_ok = True
            st.rerun()
        if st.session_state.p0_sync_ok:
            st.markdown(f'<div class="ok-bar">✅ 已同步 ΔN = <b>{st.session_state.delta_n:+d}</b> → P1 计算模块</div>',
                        unsafe_allow_html=True)
            st.session_state.p0_sync_ok = False

        # 实时故障诊断结果
        if st.session_state.p0_diag_last:
            d = st.session_state.p0_diag_last
            if d["level"] == "error":
                st.markdown(f'<div class="err-bar">🔴 <b>故障检测</b>：{d["fault"]}<br><small>{d["hint"]}</small></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="warn-bar">🟡 <b>注意</b>：{d["fault"]}<br><small>{d["hint"]}</small></div>',
                            unsafe_allow_html=True)

    with col_cam:
        st.markdown('<div class="card-title">📷 实时画面</div>', unsafe_allow_html=True)
        cam_img = st.camera_input("拍照", label_visibility="collapsed")
        preview_slot = st.empty()

        if cam_img and st.session_state.p0_counter and COUNTER_OK:
            raw = np.frombuffer(cam_img.read(), np.uint8)
            frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if frame is not None:
                result = st.session_state.p0_counter.process_frame(frame)
                st.session_state.delta_n = result.delta_n
                if result.event_triggered:
                    st.session_state.p0_history.append((
                        datetime.now().strftime("%H:%M:%S"),
                        result.delta_n, "✓", result.direction or ""
                    ))
                # 标注帧显示
                ann = cv2.cvtColor(result.annotated_frame, cv2.COLOR_BGR2RGB)
                preview_slot.image(ann, caption="干涉环采集画面（含 ROI 识别框）", width="stretch")
                st.session_state.p0_last_frame = ann

                # 置信度指标
                dir_zh = {"eject":"吐出 ⬆","absorb":"吞入 ⬇","invalid":"无事件 ─"}.get(
                    result.current_direction, "─")
                c1, c2, c3 = st.columns(3)
                c1.metric("方向", dir_zh)
                c2.metric("置信度", f"{result.confidence:.2%}")
                c3.metric("ΔN", f"{result.delta_n:+d}")

                # R007 实时故障诊断（每5帧）
                st.session_state.p0_diag_cnt += 1
                if st.session_state.p0_diag_cnt % 5 == 0:
                    st.session_state.p0_diag_last = _quick_fault_check(frame)
        elif st.session_state.p0_last_frame is not None:
            preview_slot.image(st.session_state.p0_last_frame, caption="上一帧", width="stretch")
        else:
            with preview_slot.container():
                _cam_placeholder()

    # 时序图
    if len(st.session_state.p0_history) >= 2:
        st.markdown("---")
        st.markdown('<div class="card-title">📈 ΔN 时序变化曲线</div>', unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.p0_history, columns=["时间","ΔN","事件","方向"])
        st.line_chart(df.set_index("时间")["ΔN"], height=200, use_container_width=True)
        with st.expander("📋 计数事件记录"):
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("⬇ 导出 CSV", csv, "delta_n_log.csv", "text/csv")


def _render_video_tab():
    st.markdown("""<div class="info-bar">
    🎬 <b>视频分析模式</b>：上传预录制干涉环视频，系统自动逐帧分析输出 ΔN。<br>
    ⚡ v5 优化：跳帧+多线程加速，8秒视频 ≤ 10秒处理完成。
    </div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader("上传干涉环视频", type=["mp4","avi","mov","mkv"],
                                 help="建议分辨率 ≥ 480p，帧率 ≥ 24fps")
    if not uploaded:
        st.markdown("""<div style="border:2px dashed #D0DDF5;border-radius:12px;padding:40px;
            text-align:center;color:#4A6080;margin:16px 0">
            <div style="font-size:48px;margin-bottom:12px">🎬</div>
            <div style="font-size:16px;font-weight:600">上传干涉环实验视频</div>
            <div style="font-size:13px;margin-top:8px;opacity:0.7">支持 MP4 · AVI · MOV 格式</div>
            </div>""", unsafe_allow_html=True)
        return

    cl, cr = st.columns([1,1], gap="large")
    with cl:
        st.markdown('<div class="card-title">🎬 视频预览</div>', unsafe_allow_html=True)
        st.video(uploaded)
        roi_v = st.slider("ROI 比例", 0.10, 0.50, 0.28, 0.01, key="v_roi")
        skip_v = st.slider("跳帧数（越大越快）", 1, 5, 2, 1,
                           help="每 N+1 帧处理1帧，推荐 2~3")

    with cr:
        st.markdown('<div class="card-title">📊 分析结果</div>', unsafe_allow_html=True)
        if st.button("▶ 开始视频分析", type="primary", use_container_width=True):
            suffix = os.path.splitext(uploaded.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read()); tmp_path = tmp.name
            roi_cfg = ROIConfig(roi_ratio=roi_v)
            counter = RingCounter(roi_cfg=roi_cfg)
            processor = VideoProcessor(counter)
            bar = st.progress(0, text="正在分析...")
            try:
                results = processor.process_video_file(
                    tmp_path,
                    lambda c, t: bar.progress(c/max(t,1), text=f"分析中 {c}/{t} 帧"),
                    frame_skip=skip_v
                )
                os.unlink(tmp_path)
                bar.progress(1.0, text="✅ 分析完成")
                if results:
                    final = results[-1].delta_n
                    events = [(i,r) for i,r in enumerate(results) if r.event_triggered]
                    c1,c2,c3 = st.columns(3)
                    c1.metric("最终 ΔN", f"{final:+d}")
                    c2.metric("吐出次数", sum(1 for _,r in events if r.direction=="eject"))
                    c3.metric("吞入次数", sum(1 for _,r in events if r.direction=="absorb"))
                    dn_s = [r.delta_n for r in results]
                    st.line_chart(pd.DataFrame({"ΔN":dn_s}), height=200)
                    if events:
                        with st.expander("📋 事件明细"):
                            st.dataframe(pd.DataFrame([{
                                "帧号":i,"ΔN":r.delta_n,
                                "方向":"吐出⬆" if r.direction=="eject" else "吞入⬇",
                                "置信度":f"{r.confidence:.2%}"
                            } for i,r in events]), use_container_width=True)
                    if st.button("📤 同步到 P1 计算模块", type="primary", use_container_width=True):
                        st.session_state.p1_sync_delta_n = final
                        st.session_state.delta_n = final
                        st.markdown(f'<div class="ok-bar">✅ ΔN = {final:+d} 已同步</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"❌ 分析失败：{e}")
                try: os.unlink(tmp_path)
                except: pass


def _render_image_tab():
    st.markdown("""<div class="info-bar">
    🖼 <b>图片序列模式</b>：上传多张干涉环图片（按时间顺序命名），系统按序分析变化量。
    </div>""", unsafe_allow_html=True)
    imgs = st.file_uploader("上传图片（多选，按时序命名）",
                             type=["jpg","jpeg","png","bmp"], accept_multiple_files=True)
    if not imgs:
        return
    imgs = sorted(imgs, key=lambda f: f.name)
    if st.button("▶ 分析图片序列", type="primary"):
        counter = RingCounter(); counter.start()
        data, prog, ph = [], st.progress(0), st.empty()
        for i, f in enumerate(imgs):
            raw = np.frombuffer(f.read(), np.uint8)
            frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if frame is None: continue
            r = counter.process_frame(frame)
            data.append({"文件":f.name,"ΔN":r.delta_n,"方向":r.current_direction,
                         "置信度":f"{r.confidence:.2%}","触发":"✓" if r.event_triggered else ""})
            prog.progress((i+1)/len(imgs))
            ph.image(cv2.cvtColor(r.annotated_frame, cv2.COLOR_BGR2RGB),
                     caption=f"{i+1}/{len(imgs)} · {f.name}", width="stretch")
        if data:
            final = data[-1]["ΔN"]
            st.metric("最终 ΔN", f"{final:+d}")
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            if st.button("📤 同步到 P1"):
                st.session_state.p1_sync_delta_n = final
                st.markdown(f'<div class="ok-bar">✅ ΔN = {final:+d} 已同步</div>', unsafe_allow_html=True)


def render_p0():
    _init()
    if not COUNTER_OK:
        st.warning(f"⚠ 计数模块依赖缺失：{_import_err}")

    st.markdown("""<div class="card">
    <div class="card-title" style="font-size:18px">🔢 干涉环吞吐变化量自动计数系统
      <span style="font-size:12px;font-weight:400;color:#4A6080;margin-left:10px">P0 · 传统算法 + 深度学习融合</span>
    </div>
    <div style="font-size:13px;color:#4A6080;line-height:1.9">
      计数原理：吐出1环 → ΔN +1 &nbsp;|&nbsp; 吞入1环 → ΔN −1 &nbsp;|&nbsp;
      <b>全程只输出变化量，不统计画面内总环数</b><br>
      公式：Δl = ΔN · λ/2，λ = 632.8 nm (He-Ne)
    </div></div>""", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["📷 摄像头实时计数", "🎬 视频文件分析", "🖼 图片序列分析"])
    with t1: _render_camera_tab()
    with t2: _render_video_tab()
    with t3: _render_image_tab()
