"""
pages/p1_calculator.py · v5 重构
P1 数据计算与不确定度分析

v5 优化点：
1. [视觉] 结果区用 big-display + result-highlight 突出展示 E 值
2. [智能] 输入自检：直径异常值自动标红 + 提示
3. [智能] R² < 0.99 时自动警告拟合质量
4. [智能] 相对不确定度 > 10% 自动给出优化建议
5. [交互] 数据录入全部加 help 说明，防止填错单位
6. [交互] R009 可交互公式（点击字母反算）
7. [导出] TXT + PDF 双格式报告，PDF 含图表
8. [容错] 所有输入范围限制 + 通俗化报错
9. [自动] 从 P0 同步 ΔN 时自动弹出绿色确认条
"""

import streamlit as st
import numpy as np
import pandas as pd
import math
import io
from datetime import datetime
import streamlit.components.v1 as components

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MPL_OK = True
except ImportError:
    MPL_OK = False

from modules.calculator import (
    InstrumentConfig, ExperimentParams, MeasurementData,
    calculate_youngs_modulus, least_squares_fit, uncertainty_A
)

Optional = None  # typing stub


# ──────────────────────────────────────────────
# Session init
# ──────────────────────────────────────────────
def _init():
    defs = {
        "p1_diameters":     [0.500e-3, 0.502e-3, 0.499e-3, 0.501e-3, 0.500e-3],
        "p1_fn_pairs":      [(5.0,8),(10.0,16),(15.0,25),(20.0,33),(25.0,41)],
        "p1_lambda_nm":     632.8,
        "p1_length_mm":     800.0,
        "p1_mic_um":        4.0,
        "p1_ruler_mm":      0.5,
        "p1_force_n":       0.05,
        "p1_lam_nm":        0.1,
        "p1_result":        None,
        "p1_material_hint": None,
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ──────────────────────────────────────────────
# 智能数据自检
# ──────────────────────────────────────────────
def _check_diameters(diameters_mm: list) -> list[str]:
    """检查直径数据，返回警告列表"""
    warnings = []
    if len(diameters_mm) < 3:
        warnings.append("⚠ 直径测量组数 < 3，A类不确定度可靠性低，建议至少测6次")
    arr = np.array(diameters_mm)
    mean, std = arr.mean(), arr.std()
    if std > 0 and mean > 0:
        cv = std / mean
        if cv > 0.02:
            warnings.append(f"⚠ 直径测量离散度较大（变异系数 {cv*100:.1f}%），请检查是否测量了不同截面/位置")
    outliers = [i+1 for i, v in enumerate(diameters_mm) if abs(v - mean) > 2.5 * std and std > 0]
    if outliers:
        warnings.append(f"⚠ 第 {outliers} 组数据可能为异常值（偏离均值 > 2.5σ），请核实")
    return warnings


def _guess_material(E_gpa: float) -> str:
    """根据 E 值猜测材料"""
    if 195 <= E_gpa <= 215: return "🔩 可能是钢（Steel，~200 GPa）"
    if 185 <= E_gpa <= 220: return "⚙ 可能是铁（Iron，~210 GPa）"
    if 110 <= E_gpa <= 135: return "🔶 可能是铜（Copper，~120 GPa）"
    if 65  <= E_gpa <= 80:  return "🥈 可能是铝（Aluminum，~70 GPa）"
    if 95  <= E_gpa <= 115: return "🔷 可能是黄铜（Brass，~100 GPa）"
    return "❓ 未匹配已知金属，请核实数据"


# ──────────────────────────────────────────────
# 仪器参数面板
# ──────────────────────────────────────────────
def _panel_instrument():
    st.markdown('<div class="card-title">🔧 仪器参数设置（最大允差）</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-bar">以下参数影响 B 类不确定度计算，请根据实际仪器规格填写。修改后计算结果实时更新。</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        mic = st.number_input("千分尺最大允差 Δ_d (μm)", 0.1, 50.0,
                               st.session_state.p1_mic_um, 0.1, "%.1f",
                               help="螺旋测微器（千分尺）测量金属丝直径的最大允差，常见值：4 μm")
        st.session_state.p1_mic_um = mic
        ruler = st.number_input("米尺最大允差 Δ_l (mm)", 0.1, 5.0,
                                 st.session_state.p1_ruler_mm, 0.1, "%.1f",
                                 help="钢卷尺/米尺测量金属丝原长的最大允差，常见值：0.5 mm")
        st.session_state.p1_ruler_mm = ruler
    with c2:
        force_d = st.number_input("拉力传感器最大允差 Δ_F (N)", 0.001, 1.0,
                                   st.session_state.p1_force_n, 0.001, "%.3f",
                                   help="拉力传感器的最大允差，常见值：0.05 N")
        st.session_state.p1_force_n = force_d
        lam_d = st.number_input("激光波长允差 Δ_λ (nm)", 0.01, 5.0,
                                 st.session_state.p1_lam_nm, 0.01, "%.2f",
                                 help="激光器标定波长的不确定度，He-Ne 常见值：0.1 nm")
        st.session_state.p1_lam_nm = lam_d


# ──────────────────────────────────────────────
# 固定参数面板
# ──────────────────────────────────────────────
def _panel_fixed():
    st.markdown('<div class="card-title">📐 固定实验参数</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        lam = st.number_input("激光波长 λ (nm)", 400.0, 800.0,
                               st.session_state.p1_lambda_nm, 0.1, "%.1f",
                               help="He-Ne 激光器标准波长 632.8 nm")
        st.session_state.p1_lambda_nm = lam
    with c2:
        length = st.number_input("金属丝原长 l (mm)", 100.0, 5000.0,
                                  st.session_state.p1_length_mm, 0.1, "%.1f",
                                  help="加载前金属丝的自然长度（加载点到固定点距离）")
        st.session_state.p1_length_mm = length


# ──────────────────────────────────────────────
# 直径面板
# ──────────────────────────────────────────────
def _panel_diameter():
    st.markdown('<div class="card-title">📏 金属丝直径测量数据</div>', unsafe_allow_html=True)
    st.caption("多次测量直径（单位 mm）↓ 系统自动用贝塞尔公式计算 A 类不确定度")
    n = st.number_input("测量组数", 1, 20, len(st.session_state.p1_diameters), 1, key="p1_n_dia")
    diameters_mm = []
    cols_per = 5
    for row in range(math.ceil(int(n) / cols_per)):
        cols = st.columns(cols_per)
        for ci, col in enumerate(cols):
            idx = row * cols_per + ci
            if idx >= int(n): break
            def_v = (st.session_state.p1_diameters[idx] * 1e3
                     if idx < len(st.session_state.p1_diameters) else 0.500)
            v = col.number_input(f"d{idx+1}(mm)", 0.001, 50.0,
                                  float(f"{def_v:.3f}"), 0.001, "%.3f",
                                  key=f"p1_d_{idx}")
            diameters_mm.append(v)
    st.session_state.p1_diameters = [v * 1e-3 for v in diameters_mm]

    # 实时统计 + 自检
    if len(diameters_mm) >= 2:
        arr = np.array(diameters_mm)
        mean, std, uA = uncertainty_A(list(arr * 1e-3))
        c1, c2, c3 = st.columns(3)
        c1.metric("平均值 d̄", f"{mean*1e3:.4f} mm")
        c2.metric("标准偏差 s", f"{std*1e3:.4f} mm")
        c3.metric("A类不确定度 u_A", f"{uA*1e3:.4f} mm")
        # 智能自检
        for w in _check_diameters(diameters_mm):
            st.markdown(f'<div class="warn-bar">{w}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# F-ΔN 数据面板
# ──────────────────────────────────────────────
def _panel_fn():
    st.markdown('<div class="card-title">⚖ 拉力 F 与干涉环计数 ΔN 数据</div>', unsafe_allow_html=True)

    # P0 同步提示
    if st.session_state.get("p1_sync_delta_n") is not None:
        synced = st.session_state.p1_sync_delta_n
        st.markdown(f'<div class="ok-bar">📥 收到来自 P0 的 ΔN = <b>{synced:+d}</b>，点击下方按钮导入到最后一行</div>',
                    unsafe_allow_html=True)
        if st.button("✅ 导入同步的 ΔN"):
            if st.session_state.p1_fn_pairs:
                last = list(st.session_state.p1_fn_pairs[-1])
                last[1] = synced
                st.session_state.p1_fn_pairs = list(st.session_state.p1_fn_pairs[:-1]) + [tuple(last)]
            st.session_state.p1_sync_delta_n = None
            st.rerun()

    n = st.number_input("数据组数", 2, 30, len(st.session_state.p1_fn_pairs), 1, key="p1_n_pairs")
    hc = st.columns([0.6, 1.2, 1.2])
    hc[0].markdown("**序号**"); hc[1].markdown("**拉力 F (N)**"); hc[2].markdown("**ΔN**")
    fn_pairs = []
    for i in range(int(n)):
        cols = st.columns([0.6, 1.2, 1.2])
        cols[0].markdown(f"<div style='padding-top:28px;color:#4A6080;font-size:13px'>第 {i+1} 组</div>",
                         unsafe_allow_html=True)
        def_F  = st.session_state.p1_fn_pairs[i][0] if i < len(st.session_state.p1_fn_pairs) else 5.0*(i+1)
        def_dN = st.session_state.p1_fn_pairs[i][1] if i < len(st.session_state.p1_fn_pairs) else 8*(i+1)
        F  = cols[1].number_input("", 0.0, 500.0, float(def_F), 0.1, "%.2f",
                                   key=f"p1_F_{i}", label_visibility="collapsed",
                                   help="拉力传感器示数（单位 N）")
        dN = cols[2].number_input("", -9999, 9999, int(def_dN), 1,
                                   key=f"p1_dN_{i}", label_visibility="collapsed",
                                   help="对应此拉力下的干涉环累计变化数 ΔN")
        fn_pairs.append((F, dN))
    st.session_state.p1_fn_pairs = fn_pairs


# ──────────────────────────────────────────────
# 拟合图
# ──────────────────────────────────────────────
def _chart_fit(result):
    if not MPL_OK or not result.success: return
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor("#F5F8FF"); ax.set_facecolor("#FAFCFF")
    pairs = st.session_state.p1_fn_pairs
    F_list = [p[0] for p in pairs]; dN_list = [float(p[1]) for p in pairs]
    ax.scatter(dN_list, F_list, color="#003893", s=65, zorder=5, label="Measured")
    margin = (max(dN_list)-min(dN_list)) * 0.12
    x = np.linspace(min(dN_list)-margin, max(dN_list)+margin, 200)
    ax.plot(x, result.fit_k*x+result.fit_b, color="#00B4D8", lw=2.5,
            label=f"Fit: F={result.fit_k:.4f}·ΔN+{result.fit_b:.4f}")
    # 异常点标注
    F_a = np.array(F_list); dN_a = np.array(dN_list)
    res = F_a - (result.fit_k*dN_a+result.fit_b)
    sig = np.std(res)
    for i, (x_, y_, r_) in enumerate(zip(dN_list, F_list, res)):
        if sig > 0 and abs(r_) > 2*sig:
            ax.annotate(f"⚠P{i+1}", (x_, y_), xytext=(6,6),
                        textcoords="offset points", color="#FF3B30", fontsize=9)
    ax.set_xlabel("ΔN (fringe count)", fontsize=11)
    ax.set_ylabel("F (N)", fontsize=11)
    ax.set_title(f"F-ΔN Least Squares Fit  |  R² = {result.fit_R2:.6f}", fontsize=11, color="#003893")
    ax.legend(fontsize=10); ax.grid(True, ls="--", alpha=0.4, color="#C8D8F5")
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)


# ──────────────────────────────────────────────
# 不确定度条图
# ──────────────────────────────────────────────
def _chart_unc(result):
    labels = ["2·u(d)/d", "u(l)/l", "u(λ)/λ", "u(k)/k"]
    vals = [result.rel_unc_d**2, result.rel_unc_l**2,
            result.rel_unc_lambda**2, result.rel_unc_k**2]
    total = sum(vals)
    if total < 1e-30: return
    df = pd.DataFrame({"来源": labels, "方差贡献(%)": [v/total*100 for v in vals]})
    st.bar_chart(df.set_index("来源"), height=200)


# ──────────────────────────────────────────────
# R009 可交互公式
# ──────────────────────────────────────────────
def _interactive_formula():
    components.html("""
<style>
.fw{background:linear-gradient(135deg,#f5f9ff,#eaf1ff);border:1px solid #D0DDF5;
  border-radius:12px;padding:18px 20px;font-family:'Noto Sans SC',sans-serif}
.fm{display:flex;align-items:center;justify-content:center;gap:5px;font-size:21px;flex-wrap:wrap;margin-bottom:14px}
.vb{background:#003893;color:white;border:none;border-radius:8px;padding:5px 13px;
  cursor:pointer;font-size:15px;font-weight:700;transition:all 0.15s;font-family:serif}
.vb:hover{background:#00B4D8;transform:scale(1.07)}.vb.on{background:#FF6B35}
.op{font-size:19px;color:#4A6080;font-style:italic}
.modal{display:none;background:rgba(0,0,0,0.5);position:fixed;top:0;left:0;
  width:100%;height:100%;z-index:9999;justify-content:center;align-items:center}
.modal.show{display:flex}
.mbox{background:white;border-radius:14px;padding:26px;min-width:270px;
  box-shadow:0 8px 40px rgba(0,56,147,0.3)}
.mt{font-size:15px;font-weight:700;color:#003893;margin-bottom:12px}
.mi{width:100%;padding:10px 13px;border:2px solid #003893;border-radius:8px;
  font-size:15px;box-sizing:border-box;margin-bottom:10px}
.mi:focus{outline:none;border-color:#00B4D8}
.mb{width:100%;padding:9px;background:#003893;color:white;border:none;
  border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-bottom:7px}
.mb:hover{background:#00B4D8}
.mc{width:100%;padding:9px;background:#eee;color:#333;border:none;border-radius:8px;font-size:13px;cursor:pointer}
.rb{background:#f0f4ff;border-left:4px solid #003893;border-radius:0 8px 8px 0;
  padding:11px 15px;margin-top:10px;font-size:13.5px;line-height:1.9;color:#0A1628;min-height:44px}
.uh{font-size:11px;color:#4A6080;margin-top:3px}
</style>
<div class="fw">
  <div style="font-size:12.5px;color:#4A6080;margin-bottom:10px;text-align:center">
    🖱 点击彩色字母输入已知量 → 自动求解其余量 &nbsp;|&nbsp; E = 8Fl / (π d² λ ΔN)
  </div>
  <div class="fm">
    <button class="vb" onclick="om('E')" title="杨氏模量(Pa)">E</button>
    <span class="op">=</span><span class="op">8</span>
    <button class="vb" onclick="om('F')" title="拉力(N)">F</button>
    <button class="vb" onclick="om('l')" title="原长(m)">l</button>
    <span class="op"> / (π·</span>
    <button class="vb" onclick="om('d')" title="直径(m)">d</button>
    <span class="op">²·</span>
    <button class="vb" onclick="om('λ')" title="波长(m)">λ</button>
    <span class="op">·</span>
    <button class="vb" onclick="om('ΔN')" title="干涉环变化数">ΔN</button>
    <span class="op">)</span>
    <button onclick="clearAll()" style="margin-left:10px;padding:4px 10px;border:1px solid #D0DDF5;
      border-radius:6px;background:#fff;color:#4A6080;cursor:pointer;font-size:12px">清空</button>
  </div>
  <div class="rb" id="rb">输入5个已知量后自动计算第6个</div>
</div>
<div class="modal" id="md">
<div class="mbox">
  <div class="mt" id="mt">输入数值</div>
  <div class="uh" id="mu"></div>
  <input class="mi" id="mi" type="number" step="any" placeholder="请输入数值"/>
  <button class="mb" onclick="ci()">✅ 确认</button>
  <button class="mc" onclick="cm()">取消</button>
</div></div>
<script>
const V={E:null,F:null,l:null,d:null,λ:null,ΔN:null};
const U={E:'Pa (如 2e11)',F:'N (如 9.8)',l:'m (如 0.8)',d:'m (如 0.001)',λ:'m (如 6.328e-7)',ΔN:'整数 (如 50)'};
const L={E:'杨氏模量 E',F:'拉力 F',l:'原长 l',d:'直径 d',λ:'波长 λ',ΔN:'ΔN'};
let cv=null;
function om(v){cv=v;document.getElementById('mt').textContent='输入 '+L[v];
  document.getElementById('mu').textContent='单位: '+U[v];
  document.getElementById('mi').value=V[v]!==null?V[v]:'';
  document.getElementById('md').classList.add('show');
  setTimeout(()=>document.getElementById('mi').focus(),80);}
function cm(){document.getElementById('md').classList.remove('show');}
function ci(){const v=parseFloat(document.getElementById('mi').value);
  if(!isNaN(v)&&v!==0){V[cv]=v;
    document.querySelectorAll('.vb').forEach(b=>{if(b.textContent===cv)b.classList.add('on');});
    calc();}cm();}
document.getElementById('mi').addEventListener('keydown',e=>{if(e.key==='Enter')ci();});
function clearAll(){Object.keys(V).forEach(k=>V[k]=null);
  document.querySelectorAll('.vb').forEach(b=>b.classList.remove('on'));
  document.getElementById('rb').innerHTML='输入5个已知量后自动计算第6个';}
function fmt(v,k){if(k==='E')return (v/1e9).toFixed(3)+' GPa ('+v.toExponential(3)+' Pa)';
  if(k==='λ')return v.toExponential(3)+' m';if(k==='d')return (v*1000).toFixed(4)+' mm';return v;}
function calc(){
  const {E,F,l,d,λ,ΔN}=V,π=Math.PI;
  const known=Object.values(V).filter(v=>v!==null).length;
  let lines=[];
  for(const[k,v]of Object.entries(V))if(v!==null)lines.push(`已知 ${k} = ${fmt(v,k)}`);
  if(known>=5){
    let res='';
    if(E===null&&F&&l&&d&&λ&&ΔN)res='E = '+(8*F*l/(π*d*d*λ*ΔN)/1e9).toFixed(3)+' GPa';
    else if(F===null&&E&&l&&d&&λ&&ΔN)res='F = '+(E*π*d*d*λ*ΔN/(8*l)).toFixed(4)+' N';
    else if(ΔN===null&&E&&F&&l&&d&&λ)res='ΔN = '+(8*F*l/(E*π*d*d*λ)).toFixed(1);
    else if(d===null&&E&&F&&l&&λ&&ΔN)res='d = '+(Math.sqrt(8*F*l/(E*π*λ*ΔN))*1000).toFixed(4)+' mm';
    else if(l===null&&E&&F&&d&&λ&&ΔN)res='l = '+(E*π*d*d*λ*ΔN/(8*F)).toFixed(4)+' m';
    else if(λ===null&&E&&F&&l&&d&&ΔN)res='λ = '+(8*F*l/(E*π*d*d*ΔN)*1e9).toFixed(2)+' nm';
    else res='⚠ 当前组合无法直接求解，请换一个未知量';
    lines.push('');lines.push('📊 <b>计算结果：'+res+'</b>');
  }else lines.push(`<br>⏳ 还需输入 ${5-known} 个已知量`);
  document.getElementById('rb').innerHTML=lines.join('<br>');
}
</script>""", height=360, scrolling=False)


# ──────────────────────────────────────────────
# PDF 报告
# ──────────────────────────────────────────────
def _gen_pdf(result, params) -> bytes | None:
    try:
        from fpdf import FPDF
        pdf = FPDF(); pdf.add_page()
        pdf.set_font("Helvetica","B",16)
        pdf.cell(0,12,"Young's Modulus Experiment Report",ln=True,align="C")
        pdf.set_font("Helvetica","",10)
        pdf.cell(0,8,f"Shenzhen Technology University | {datetime.now().strftime('%Y-%m-%d %H:%M')}",ln=True,align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica","B",13)
        pdf.set_fill_color(0,56,147); pdf.set_text_color(255,255,255)
        pdf.cell(0,10,f"  E = ({result.E_value/1e9:.2f} +/- {result.E_abs_unc/1e9:.2f}) GPa  |  u_E/E = {result.E_rel_unc*100:.2f}%",ln=True,fill=True)
        pdf.set_text_color(0,0,0); pdf.ln(3)
        pdf.set_font("Courier","",8)
        for line in result.report_lines:
            safe = line.encode('latin-1','replace').decode('latin-1')
            pdf.cell(0,4.5,safe,ln=True)
        return bytes(pdf.output())
    except Exception:
        return None


# ──────────────────────────────────────────────
# 主渲染
# ──────────────────────────────────────────────
def render_p1():
    _init()
    st.markdown("""<div class="card">
    <div class="card-title" style="font-size:18px">📊 实验数据智能计算与不确定度分析系统
      <span style="font-size:12px;font-weight:400;color:#4A6080;margin-left:10px">P1 · 严格遵循国内普通大学物理实验规范</span>
    </div>
    <div style="font-size:13px;color:#4A6080;line-height:1.9">
      核心公式：<b>E = 8Fl / (π d² λ ΔN)</b> &nbsp;|&nbsp;
      不确定度：A类（贝塞尔公式）+ B类（仪器允差）→ 方和根合成
    </div></div>""", unsafe_allow_html=True)

    col_in, col_out = st.columns([1.1, 1], gap="large")

    with col_in:
        with st.expander("🔧 仪器参数设置（最大允差）", expanded=True):
            _panel_instrument()
        with st.expander("📐 固定实验参数", expanded=True):
            _panel_fixed()
        with st.expander("📏 金属丝直径测量", expanded=True):
            _panel_diameter()
        with st.expander("⚖ F-ΔN 测量数据", expanded=True):
            _panel_fn()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⚡ 一键计算杨氏模量", type="primary", use_container_width=True):
            inst = InstrumentConfig(
                micrometer_delta  =st.session_state.p1_mic_um * 1e-6,
                ruler_delta       =st.session_state.p1_ruler_mm * 1e-3,
                force_sensor_delta=st.session_state.p1_force_n,
                lambda_delta      =st.session_state.p1_lam_nm * 1e-9,
            )
            params = ExperimentParams(
                lambda_m      =st.session_state.p1_lambda_nm * 1e-9,
                wire_length_m =st.session_state.p1_length_mm * 1e-3,
            )
            mdata = MeasurementData(
                diameters          =st.session_state.p1_diameters,
                force_delta_n_pairs=st.session_state.p1_fn_pairs,
            )
            with st.spinner("正在计算…"):
                result = calculate_youngs_modulus(mdata, params, inst)
            st.session_state.p1_result = result

    with col_out:
        st.markdown('<div class="card-title">📈 计算结果</div>', unsafe_allow_html=True)
        result = st.session_state.p1_result

        if result is None:
            st.markdown("""<div style="text-align:center;padding:60px 20px;color:#4A6080">
            <div style="font-size:52px;margin-bottom:16px">⚡</div>
            <div style="font-size:16px">填写左侧参数后<br>点击「一键计算」</div></div>""",
                        unsafe_allow_html=True)

        elif not result.success:
            # 通俗化报错
            err = result.error_msg
            friendly = {
                "至少输入": "💡 请先填写测量数据（直径至少1组，F-ΔN至少2组）",
                "不合法":  "💡 请检查数据是否填写正确（直径/波长/斜率必须为正数）",
            }
            msg = next((v for k, v in friendly.items() if k in err), f"❌ {err}")
            st.markdown(f'<div class="err-bar">{msg}<br><small>详细：{err}</small></div>',
                        unsafe_allow_html=True)

        else:
            # ── 核心结果大字显示 ──
            cls = "pos" if result.E_value > 0 else ""
            st.markdown(f"""<div class="big-display">
              <div class="big-label">杨氏模量 E</div>
              <div class="big-value {cls}">{result.E_value/1e9:.2f}</div>
              <div class="big-unit">GPa</div>
              <div class="big-sub">
                ({result.E_value/1e9:.2f} ± {result.E_abs_unc/1e9:.2f}) GPa
                &nbsp;|&nbsp; u_E/E = {result.E_rel_unc*100:.2f}%
              </div>
            </div>""", unsafe_allow_html=True)

            # 材料猜测
            mat = _guess_material(result.E_value / 1e9)
            st.markdown(f'<div class="result-highlight" style="background:linear-gradient(135deg,rgba(0,56,147,0.07),rgba(0,180,216,0.07));border:1.5px solid rgba(0,180,216,0.3);border-radius:12px;padding:14px 18px;margin:10px 0;font-size:14px">{mat}</div>',
                        unsafe_allow_html=True)

            # 智能提醒
            if result.E_rel_unc > 0.10:
                st.markdown(f'<div class="warn-bar">⚠ 相对不确定度 {result.E_rel_unc*100:.1f}% 偏大（建议 &lt;5%）。<br>主要来源：{["2·u(d)/d","u(l)/l","u(λ)/λ","u(k)/k"][np.argmax([result.rel_unc_d**2,result.rel_unc_l**2,result.rel_unc_lambda**2,result.rel_unc_k**2])]}，请增加该量的测量次数或使用更精密仪器。</div>',
                             unsafe_allow_html=True)
            if result.fit_R2 < 0.99:
                st.markdown(f'<div class="warn-bar">⚠ F-ΔN 拟合相关系数 R²={result.fit_R2:.4f} 偏低。请检查是否存在数据录入错误或系统误差（如未消除空程）。</div>',
                             unsafe_allow_html=True)

            # 指标卡
            c1, c2 = st.columns(2)
            c1.metric("直径均值 d̄", f"{result.d_mean*1e3:.4f} mm",
                      f"u_c = {result.d_uc*1e6:.2f} μm")
            c2.metric("拟合斜率 k", f"{result.fit_k:.4f} N/环",
                      f"R² = {result.fit_R2:.5f}")

            # 不确定度贡献图
            st.markdown("**不确定度来源（方差贡献比）**")
            _chart_unc(result)

            # 拟合图
            st.markdown("**F-ΔN 最小二乘拟合**")
            _chart_fit(result)

            # 完整报告
            with st.expander("📋 完整计算报告（大学物理实验格式）"):
                rpt = "\n".join(result.report_lines)
                st.code(rpt, language=None)
                c_e1, c_e2 = st.columns(2)
                c_e1.download_button("⬇ TXT 报告", rpt.encode("utf-8"),
                    f"ym_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    "text/plain", use_container_width=True)
                pdf_b = _gen_pdf(result, None)
                if pdf_b:
                    c_e2.download_button("⬇ PDF 报告", pdf_b,
                        f"ym_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        "application/pdf", use_container_width=True)
                else:
                    c_e2.info("PDF 需安装 fpdf2")

    # ── 底部可交互公式 ──
    st.markdown("---")
    st.markdown('<div class="card-title">📐 核心公式 · 可交互反算</div>', unsafe_allow_html=True)
    _interactive_formula()

    with st.expander("📖 完整公式推导体系"):
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.latex(r"\frac{4F}{\pi d^2}=E\frac{\Delta l}{l}")
            st.caption("胡克定律（1）"); st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.latex(r"E=\frac{\pi d^2 \Delta l}{4Fl}")
            st.caption("杨氏模量（2）"); st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.latex(r"\Delta l=\Delta N \frac{\lambda}{2}")
            st.caption("干涉形变（3）"); st.markdown('</div>', unsafe_allow_html=True)
        with c4:
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.latex(r"E=\frac{8Fl}{\pi d^2 \lambda \Delta N}")
            st.caption("最终公式（4）"); st.markdown('</div>', unsafe_allow_html=True)
