"""
app.py · 迈克尔逊干涉法测金属杨氏模量 · v5.0 全面重构版
深圳技术大学大学物理实验竞赛参赛项目

v5 重构亮点：
1. CSS Design Token 系统 - 所有颜色/尺寸一处管理
2. 顶栏实时显示 ΔN 状态徽章
3. 侧边栏 Step 引导（Step1→4 实验流程）
4. 全局异常捕获兜底，用户友好报错
5. 页面加载动画 fadeUp
"""

import streamlit as st

st.set_page_config(
    page_title="迈克尔逊干涉测杨氏模量 · 深圳技术大学",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "SZTU 大学物理实验竞赛 v5.0"}
)

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;600&family=Orbitron:wght@600;800&display=swap');
:root {
  --c-blue:#003893;--c-blue-mid:#0050c8;--c-blue-lt:#1a6ee8;
  --c-cyan:#00B4D8;--c-cyan-lt:#48CAE4;--c-white:#FFFFFF;
  --c-bg:#EEF3FB;--c-card:#FFFFFF;--c-card-alt:#F5F8FF;--c-border:#D0DDF5;
  --c-text:#0A1628;--c-sub:#4A6080;--c-muted:#8A9AB8;
  --c-ok:#00C896;--c-warn:#FFB300;--c-err:#FF3B30;--c-accent:#FF6B35;
  --f-sans:'Noto Sans SC',sans-serif;--f-mono:'JetBrains Mono',monospace;--f-display:'Orbitron',sans-serif;
  --r:12px;--r-lg:18px;
  --sh:0 2px 16px rgba(0,56,147,0.08);--sh-lg:0 6px 32px rgba(0,56,147,0.14);--sh-glow:0 0 24px rgba(0,180,216,0.25);
}
html,body,[class*="css"]{font-family:var(--f-sans);color:var(--c-text);}
.stApp{background:var(--c-bg);}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:0.5rem!important;max-width:1400px;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--c-bg);}
::-webkit-scrollbar-thumb{background:var(--c-cyan);border-radius:3px;}

.sztu-navbar{background:linear-gradient(130deg,var(--c-blue) 0%,#0044bb 60%,#005ecc 100%);
  padding:14px 28px;border-radius:0 0 var(--r-lg) var(--r-lg);margin-bottom:20px;
  display:flex;align-items:center;gap:16px;box-shadow:var(--sh-lg);position:relative;overflow:hidden;}
.sztu-navbar::before{content:'';position:absolute;top:-60px;right:-40px;width:200px;height:200px;
  background:radial-gradient(circle,rgba(0,180,216,0.2) 0%,transparent 70%);border-radius:50%;}
.nav-school{font-family:var(--f-display);font-size:11px;letter-spacing:2.5px;opacity:0.7;color:white;}
.nav-title{font-size:19px;font-weight:800;color:white;letter-spacing:0.5px;}
.nav-badge{margin-left:auto;background:rgba(0,180,216,0.22);border:1px solid rgba(0,180,216,0.5);
  color:var(--c-cyan-lt);padding:4px 14px;border-radius:20px;font-family:var(--f-mono);font-size:12px;}
.nav-dn{background:rgba(0,200,150,0.18);border:1px solid rgba(0,200,150,0.38);color:#00e6aa;
  padding:4px 12px;border-radius:20px;font-family:var(--f-mono);font-size:13px;font-weight:700;}

.card{background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--r);
  padding:20px 24px;box-shadow:var(--sh);margin-bottom:14px;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;width:3px;height:100%;
  background:linear-gradient(180deg,var(--c-blue),var(--c-cyan));}
.card-title{font-size:15px;font-weight:700;color:var(--c-blue);margin-bottom:14px;display:flex;align-items:center;gap:8px;}

.big-display{background:linear-gradient(135deg,#001540 0%,#002878 100%);
  border:1.5px solid var(--c-cyan);border-radius:var(--r-lg);padding:22px 24px;
  text-align:center;box-shadow:var(--sh-glow),var(--sh-lg);}
.big-label{font-family:var(--f-mono);font-size:12px;color:var(--c-cyan);letter-spacing:3px;text-transform:uppercase;margin-bottom:6px;}
.big-value{font-family:var(--f-display);font-size:64px;font-weight:800;color:#fff;line-height:1;text-shadow:0 0 24px rgba(0,180,216,0.5);}
.big-value.pos{color:var(--c-ok);text-shadow:0 0 24px rgba(0,200,150,0.5);}
.big-value.neg{color:var(--c-err);text-shadow:0 0 24px rgba(255,59,48,0.5);}
.big-unit{font-family:var(--f-mono);font-size:13px;color:rgba(255,255,255,0.45);margin-top:6px;}
.big-sub{font-size:12px;color:rgba(255,255,255,0.5);margin-top:10px;}

.pill{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:20px;
  font-size:12px;font-weight:600;font-family:var(--f-mono);}
.pill-run{background:rgba(0,200,150,0.12);color:var(--c-ok);border:1px solid rgba(0,200,150,0.28);}
.pill-pause{background:rgba(255,179,0,0.12);color:var(--c-warn);border:1px solid rgba(255,179,0,0.28);}
.pill-stop{background:rgba(74,96,128,0.10);color:var(--c-sub);border:1px solid rgba(74,96,128,0.18);}
.pill-info{background:rgba(0,84,200,0.10);color:var(--c-blue-lt);border:1px solid rgba(0,84,200,0.2);}
@keyframes blink2{0%,100%{opacity:1}50%{opacity:0.3}}
.pill-run::before{content:'● ';animation:blink2 1.6s infinite;}

.formula-box{background:linear-gradient(135deg,#f5f9ff,#eaf1ff);border:1px solid var(--c-border);
  border-radius:var(--r);padding:18px;text-align:center;margin:10px 0;}
.info-bar{background:rgba(0,56,147,0.06);border-left:4px solid var(--c-blue);
  border-radius:0 8px 8px 0;padding:11px 16px;font-size:13.5px;color:var(--c-sub);margin:10px 0;line-height:1.7;}
.warn-bar{background:rgba(255,179,0,0.08);border-left:4px solid var(--c-warn);
  border-radius:0 8px 8px 0;padding:11px 16px;font-size:13.5px;color:#7a5800;margin:10px 0;}
.err-bar{background:rgba(255,59,48,0.08);border-left:4px solid var(--c-err);
  border-radius:0 8px 8px 0;padding:11px 16px;font-size:13.5px;color:#8b0000;margin:10px 0;}
.ok-bar{background:rgba(0,200,150,0.08);border-left:4px solid var(--c-ok);
  border-radius:0 8px 8px 0;padding:11px 16px;font-size:13.5px;color:#005c40;margin:10px 0;}

.step-item{display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;}
.step-num{width:24px;height:24px;border-radius:50%;flex-shrink:0;display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:700;font-family:var(--f-mono);}
.step-active{background:var(--c-cyan);color:#001540;}
.step-done{background:var(--c-ok);color:#001540;}
.step-pending{background:rgba(255,255,255,0.15);color:rgba(255,255,255,0.5);}
.step-text{font-size:12.5px;color:rgba(255,255,255,0.82);line-height:1.5;}
.step-text b{color:white;}

.stButton>button{border-radius:9px!important;font-family:var(--f-sans)!important;
  font-weight:600!important;transition:all 0.18s ease!important;}
.stButton>button:hover{transform:translateY(-1px);box-shadow:var(--sh)!important;}
.stNumberInput>div>div>input,.stTextInput>div>div>input{border-radius:8px!important;
  border:1.5px solid var(--c-border)!important;font-family:var(--f-mono)!important;font-size:14px!important;}
[data-testid="stSidebar"]{background:linear-gradient(175deg,var(--c-blue) 0%,#001f5c 100%);}
[data-testid="stSidebar"] *{color:rgba(255,255,255,0.88)!important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.12)!important;}
[data-testid="stMetric"]{background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--r);padding:14px 16px;}
[data-testid="stMetricLabel"]{color:var(--c-sub)!important;font-size:12px!important;}
[data-testid="stMetricValue"]{color:var(--c-blue)!important;font-family:var(--f-mono)!important;font-size:20px!important;font-weight:700!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--c-bg);border-radius:var(--r);gap:3px;padding:4px;}
.stTabs [data-baseweb="tab"]{border-radius:8px!important;font-weight:600;color:var(--c-sub);font-size:13.5px;padding:8px 18px;}
.stTabs [aria-selected="true"]{background:var(--c-blue)!important;color:white!important;}
.stDataFrame{border-radius:var(--r);overflow:hidden;}
thead tr th{background:var(--c-blue)!important;color:white!important;}
[data-testid="stExpander"]{border:1px solid var(--c-border)!important;border-radius:var(--r)!important;box-shadow:none!important;}
.stProgress>div>div{background:linear-gradient(90deg,var(--c-blue),var(--c-cyan))!important;border-radius:4px!important;}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.fade-in{animation:fadeUp 0.32s ease forwards;}
.result-highlight{background:linear-gradient(135deg,rgba(0,56,147,0.07),rgba(0,180,216,0.07));
  border:1.5px solid rgba(0,180,216,0.3);border-radius:var(--r);padding:16px 20px;margin:10px 0;}
.roi-overlay{border:2px solid var(--c-cyan);border-radius:50%;box-shadow:0 0 14px rgba(0,180,216,0.4);}
</style>
"""

# CSS class aliases exported for pages to use
# (pages import: from app import CARD, CARD_TITLE, etc.)
CARD       = "card"
CARD_TITLE = "card-title"
INFO       = "info-bar"
WARN       = "warn-bar"
ERR        = "err-bar"
OK         = "ok-bar"


def _navbar_html():
    dn = st.session_state.get("delta_n", 0)
    return f"""
<div class="sztu-navbar fade-in" style="z-index:1">
  <div style="display:flex;flex-direction:column;gap:2px;z-index:1">
    <div class="nav-school">Shenzhen Technology University · 深圳技术大学</div>
    <div class="nav-title">🔬 迈克尔逊干涉法测金属杨氏模量 一体化实验系统</div>
  </div>
  <div style="margin-left:auto;display:flex;gap:10px;align-items:center;z-index:1;flex-shrink:0">
    <span class="nav-dn">ΔN = {dn:+d}</span>
    <span class="nav-badge">v5.0 · 竞赛版</span>
  </div>
</div>
"""


def _init_session():
    defaults = {
        "delta_n": 0, "count_history": [], "counting_state": "stopped",
        "last_direction": None, "p1_sync_delta_n": None,
        "lambda_nm": 632.8, "wire_length_mm": 800.0, "exp_step": 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:18px 0 8px">
          <div style="font-size:36px">🎓</div>
          <div style="font-size:14px;font-weight:800;letter-spacing:1px">深圳技术大学</div>
          <div style="font-size:11px;opacity:0.5;margin-top:3px">大学物理实验竞赛 · 2025</div>
        </div><hr>""", unsafe_allow_html=True)

        page = st.radio("功能模块", options=[
            "🔢 P0 · 干涉环计数",
            "📊 P1 · 数据计算分析",
            "🤖 P2 · 创创智能助手",
            "🔧 P3 · 故障智能诊断",
        ], key="nav_page")

        # Step 引导
        step = st.session_state.get("exp_step", 1)
        steps = [("1","P0 计数","用摄像头或视频获取 ΔN"),("2","P1 计算","一键计算杨氏模量 E"),
                 ("3","P3 诊断","拍照自动识别故障"),("4","P2 问答","问创创任何实验问题")]
        st.markdown('<hr><div style="font-size:11px;opacity:0.45;letter-spacing:1px;margin-bottom:10px">📋 实验流程</div>', unsafe_allow_html=True)
        for i, (num, title, desc) in enumerate(steps):
            si = i + 1
            cls = "step-done" if si < step else ("step-active" if si == step else "step-pending")
            icon = "✓" if si < step else num
            st.markdown(f'<div class="step-item"><div class="step-num {cls}">{icon}</div><div class="step-text"><b>{title}</b><br>{desc}</div></div>', unsafe_allow_html=True)

        dn = st.session_state.get("delta_n", 0)
        s  = st.session_state.get("counting_state", "stopped")
        pm = {"running":("pill-run","计数中"),"paused":("pill-pause","已暂停"),"stopped":("pill-stop","未启动")}
        pc, pt = pm.get(s, ("pill-stop","未启动"))
        st.markdown(f'<hr><span class="pill {pc}" style="font-size:11px">{pt}</span><div style="font-size:12px;opacity:0.6;margin-top:6px">ΔN = <b style="color:white">{dn:+d}</b></div>', unsafe_allow_html=True)
        st.markdown('<hr><div style="font-size:11px;opacity:0.4;text-align:center;line-height:1.9">Python · Streamlit · OpenCV<br>智谱AI GLM-4 · Vercel Cloud<br>© 2025 SZTU PhysLab · v5.0</div>', unsafe_allow_html=True)
    return page


def main():
    _init_session()
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(_navbar_html(), unsafe_allow_html=True)

    try:
        from modules.qr_util import render_qr_banner
        render_qr_banner(port=8501)
    except Exception:
        pass

    page = _render_sidebar()

    try:
        if page.startswith("🔢"):
            st.session_state.exp_step = max(st.session_state.exp_step, 1)
            from pages.p0_counter import render_p0;  render_p0()
        elif page.startswith("📊"):
            st.session_state.exp_step = max(st.session_state.exp_step, 2)
            from pages.p1_calculator import render_p1; render_p1()
        elif page.startswith("🤖"):
            st.session_state.exp_step = max(st.session_state.exp_step, 4)
            from pages.p2_agent import render_p2;     render_p2()
        elif page.startswith("🔧"):
            st.session_state.exp_step = max(st.session_state.exp_step, 3)
            from pages.p3_diagnosis import render_p3; render_p3()
    except Exception as e:
        st.error(f"⚠️ 页面加载异常，请刷新重试：{e}")
        import traceback
        with st.expander("🔍 详细错误（开发调试）"):
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
