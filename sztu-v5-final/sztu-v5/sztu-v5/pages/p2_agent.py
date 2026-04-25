"""
pages/p2_agent.py
智谱AI · v4.0 竞赛版
R002: 语音100%触发修复
R004: 吉祥物图片自定义上传
R005: 语音打断
"""

import streamlit as st
import re
import base64

DEFAULT_KNOWLEDGE = """
## 迈克尔逊干涉测杨氏模量实验知识库

### 基本原理
1. **杨氏模量定义**：E = σ/ε = (F/A)/(ΔL/L)
2. **迈克尔逊干涉原理**：ΔL = ΔN·λ/2
3. **核心公式**：E = 8Fl/(π d² λ ΔN)

### 实验操作步骤
1. 安装金属丝，调节张力至自然伸直状态
2. 调整迈克尔逊干涉仪：调节M1/M2镜使干涉环清晰、圆形、居中
3. 逐步增加砝码，记录每次加载后的 ΔN 值
4. 重复3次取平均，利用最小二乘法拟合 F-ΔN 直线

### 常见故障及解决
- **干涉环椭圆**：M1/M2不垂直，调节调整螺丝
- **无干涉条纹**：光路不通，检查各反射镜角度
- **干涉环不移动**：微调手轮有空程，正向旋转消除空程后重新测量
- **条纹模糊**：调整扩束镜位置和聚焦，减小外界振动

### 不确定度分析
- A类（贝塞尔公式）：多次测量的随机误差
- B类（仪器允差）：千分尺 ±4μm，米尺 ±0.5mm，力传感器 ±0.05N
- 合成：方和根法则，最大误差来源通常是直径d（贡献系数2）

### 参考值
- 钢：约 200 GPa；铜：约 120 GPa；铝：约 70 GPa；铁：约 210 GPa
"""

# ── R002/R005 语音控制 JS ──
SPEECH_JS = """
let _ccAudio = null;
let _ccMouthTimer = null;
let _ccSpeaking = false;
let _ccPaused = false;
let _ccCurrentText = '';
let mouthOpen = 0;
let isSpeaking = false;

function _setStatus(s){const e=document.getElementById('ccStatus');if(e)e.textContent=s;}
function _setBtnPause(t){const e=document.getElementById('btnPause');if(e)e.textContent=t;}

// R005: 任意时刻打断所有语音
function stopAllSpeech(){
  if(_ccAudio){_ccAudio.pause();_ccAudio.currentTime=0;_ccAudio=null;}
  if(window.speechSynthesis)window.speechSynthesis.cancel();
  if(_ccMouthTimer){clearInterval(_ccMouthTimer);_ccMouthTimer=null;}
  mouthOpen=0;isSpeaking=false;_ccSpeaking=false;_ccPaused=false;
  _setStatus('⏹ 已停止');_setBtnPause('⏸ 暂停');
}

// R002: speechSynthesis 兜底，cancel后150ms延迟确保100%触发
function _fallbackSpeak(text,lang){
  if(!window.speechSynthesis)return;
  window.speechSynthesis.cancel();
  setTimeout(()=>{
    const u=new SpeechSynthesisUtterance(text);
    u.lang=lang||'zh-CN';u.rate=0.9;u.pitch=1.1;
    isSpeaking=true;_ccSpeaking=true;
    _setStatus('🔊 播放中...');
    let t=0;
    _ccMouthTimer=setInterval(()=>{t+=0.35;mouthOpen=(Math.sin(t)*0.5+0.5)*0.85;},55);
    u.onend=u.onerror=()=>{
      clearInterval(_ccMouthTimer);_ccMouthTimer=null;
      mouthOpen=0;isSpeaking=false;_ccSpeaking=false;
      _setStatus('✅ 播放完毕');
    };
    window.speechSynthesis.speak(u);
  },150);
}

function playAudioB64(b64,text){
  stopAllSpeech();
  _ccCurrentText=text;
  try{
    const bytes=atob(b64),ab=new ArrayBuffer(bytes.length),ia=new Uint8Array(ab);
    for(let i=0;i<bytes.length;i++)ia[i]=bytes.charCodeAt(i);
    const url=URL.createObjectURL(new Blob([ab],{type:'audio/mp3'}));
    _ccAudio=new Audio(url);
    isSpeaking=true;_ccSpeaking=true;
    document.getElementById('ccSubtitle').innerHTML=text;
    _setStatus('🔊 播放中...');
    let t=0;_ccMouthTimer=setInterval(()=>{t+=0.35;mouthOpen=(Math.sin(t)*0.5+0.5)*0.85;},55);
    _ccAudio.onended=()=>{
      clearInterval(_ccMouthTimer);_ccMouthTimer=null;
      mouthOpen=0;isSpeaking=false;_ccSpeaking=false;
      _setStatus('✅ 播放完毕');_setBtnPause('⏸ 暂停');
      URL.revokeObjectURL(url);
    };
    _ccAudio.onerror=()=>{
      clearInterval(_ccMouthTimer);_ccMouthTimer=null;
      mouthOpen=0;isSpeaking=false;
      _setStatus('⚠ 切换系统语音');
      _fallbackSpeak(_ccCurrentText,'zh-CN');
    };
    _ccAudio.play().catch(()=>_fallbackSpeak(text,'zh-CN'));
  }catch(e){_fallbackSpeak(text,'zh-CN');}
}

function pauseResumeSpeech(){
  if(_ccAudio){
    if(_ccPaused){_ccAudio.play();_ccPaused=false;_setStatus('🔊 播放中...');_setBtnPause('⏸ 暂停');}
    else{_ccAudio.pause();_ccPaused=true;clearInterval(_ccMouthTimer);_ccMouthTimer=null;mouthOpen=0;_setStatus('⏸ 已暂停');_setBtnPause('▶ 继续');}
    return;
  }
  if(window.speechSynthesis){
    if(_ccPaused){window.speechSynthesis.resume();_ccPaused=false;_setStatus('🔊 播放中...');_setBtnPause('⏸ 暂停');}
    else{window.speechSynthesis.pause();_ccPaused=true;_setStatus('⏸ 已暂停');_setBtnPause('▶ 继续');}
  }
}
function replaySpeech(){if(_ccCurrentText){stopAllSpeech();setTimeout(()=>_fallbackSpeak(_ccCurrentText,'zh-CN'),100);}}
function stopSpeech(){stopAllSpeech();}

window.addEventListener('message',(e)=>{
  if(!e.data)return;
  if(e.data.type==='cc_speak_b64')playAudioB64(e.data.b64,e.data.text);
  else if(e.data.type==='cc_speak_fallback'){stopAllSpeech();setTimeout(()=>{
    document.getElementById('ccSubtitle').innerHTML=e.data.text;
    _fallbackSpeak(e.data.text,e.data.lang||'zh-CN');
  },100);}
  else if(e.data.type==='cc_stop')stopAllSpeech();
});
"""

CC_CANVAS_JS = """
const canvas=document.getElementById('ccCanvas');
const ctx=canvas.getContext('2d');
const W=canvas.width,H=canvas.height;
let blinkVal=1,animFrame,blinkTimer;
const particles=Array.from({length:18},()=>({
  x:Math.random()*W,y:Math.random()*H,r:Math.random()*2+0.5,
  vx:(Math.random()-0.5)*0.4,vy:(Math.random()-0.5)*0.4,alpha:Math.random()*0.5+0.2}));
function drawParticles(){particles.forEach(p=>{ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(0,180,216,${p.alpha})`;ctx.fill();p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;});}
function drawCC(mouth){
  ctx.clearRect(0,0,W,H);drawParticles();
  const cx=W/2,cy=H/2-10;
  const glow=ctx.createRadialGradient(cx,cy,30,cx,cy,110);
  glow.addColorStop(0,'rgba(0,180,216,0.15)');glow.addColorStop(1,'rgba(0,180,216,0)');
  ctx.beginPath();ctx.arc(cx,cy,110,0,Math.PI*2);ctx.fillStyle=glow;ctx.fill();
  const bg=ctx.createRadialGradient(cx-10,cy-15,20,cx,cy,80);
  bg.addColorStop(0,'#1a5fcc');bg.addColorStop(1,'#003893');
  ctx.beginPath();ctx.ellipse(cx,cy+30,55,45,0,0,Math.PI*2);ctx.fillStyle=bg;ctx.fill();
  const hg=ctx.createRadialGradient(cx-8,cy-35,10,cx,cy-28,52);
  hg.addColorStop(0,'#4a8fe8');hg.addColorStop(0.5,'#0055cc');hg.addColorStop(1,'#003893');
  ctx.beginPath();ctx.ellipse(cx,cy-28,52,50,0,0,Math.PI*2);ctx.fillStyle=hg;ctx.fill();
  [-52,52].forEach((dx,i)=>{const s=i===0?-1:1;
    ctx.beginPath();ctx.ellipse(cx+dx,cy-42,10,14,s*0.3,0,Math.PI*2);ctx.fillStyle='#002d80';ctx.fill();
    ctx.beginPath();ctx.ellipse(cx+dx,cy-44,5,8,s*0.3,0,Math.PI*2);ctx.fillStyle='rgba(0,180,216,0.4)';ctx.fill();});
  const eyeY=cy-32;
  [-22,22].forEach(dx=>{
    ctx.beginPath();ctx.ellipse(cx+dx,eyeY,14,14*blinkVal+1,0,0,Math.PI*2);ctx.fillStyle='white';ctx.fill();
    if(blinkVal>0.1){ctx.beginPath();ctx.ellipse(cx+dx+1,eyeY+1,8,8*blinkVal,0,0,Math.PI*2);ctx.fillStyle='#003893';ctx.fill();
      ctx.beginPath();ctx.ellipse(cx+dx-3,eyeY-3,3,3*blinkVal,0,0,Math.PI*2);ctx.fillStyle='rgba(255,255,255,0.85)';ctx.fill();}});
  ctx.beginPath();ctx.moveTo(cx,cy-14);ctx.lineTo(cx-4,cy-8);ctx.lineTo(cx+4,cy-8);ctx.closePath();ctx.fillStyle='rgba(0,180,216,0.6)';ctx.fill();
  const mH=Math.max(3,mouth*20);
  ctx.beginPath();ctx.ellipse(cx,cy-2,22,mH,0,0,Math.PI);ctx.fillStyle=mouth>0.05?'#001a4d':'rgba(255,255,255,0.15)';ctx.fill();
  ctx.strokeStyle='rgba(255,255,255,0.5)';ctx.lineWidth=1.5;ctx.stroke();
  if(mouth>0.2){ctx.beginPath();ctx.ellipse(cx,cy,15,Math.min(mH*0.5,7),0,0,Math.PI);ctx.fillStyle='rgba(255,255,255,0.85)';ctx.fill();}
  if(isSpeaking){ctx.beginPath();ctx.arc(cx,cy-28,58,0,Math.PI*2);ctx.strokeStyle=`rgba(0,180,216,${0.3+mouth*0.4})`;ctx.lineWidth=3;ctx.stroke();}
  ctx.font='600 11px Orbitron,monospace';ctx.fillStyle='rgba(0,180,216,0.7)';ctx.textAlign='center';ctx.fillText('创创 · SZTU',cx,H-14);}
function scheduleBlink(){blinkTimer=setTimeout(()=>{let t=0;const b=setInterval(()=>{t+=0.2;blinkVal=Math.abs(Math.cos(t*Math.PI));if(t>=1){clearInterval(b);blinkVal=1;}},40);scheduleBlink();},2000+Math.random()*4000);}
function animate(){drawCC(mouthOpen);animFrame=requestAnimationFrame(animate);}
animate();scheduleBlink();drawCC(0);
"""


def _build_avatar_html(custom_b64=None):
    if custom_b64:
        avatar = f"""
<div style="position:relative;width:260px;height:280px;margin:0 auto;border-radius:16px;overflow:hidden;
            background:linear-gradient(135deg,#001a4d,#002d80);box-shadow:0 0 30px rgba(0,180,216,0.3)">
  <img src="data:image/png;base64,{custom_b64}" style="width:100%;height:100%;object-fit:cover"/>
  <div id="ccGlow" style="position:absolute;inset:0;border-radius:16px;border:3px solid transparent;pointer-events:none;transition:all 0.2s"></div>
  <div style="position:absolute;bottom:10px;left:0;right:0;text-align:center;font:600 11px Orbitron,monospace;color:rgba(0,180,216,0.9)">创创 · SZTU</div>
</div>
<script>
(function(){{
  function glowLoop(){{
    const g=document.getElementById('ccGlow');
    if(g&&isSpeaking){{
      const v=(Math.sin(Date.now()/200)*0.5+0.5);
      g.style.border=`3px solid rgba(0,180,216,${0.3+v*0.5})`;
      g.style.boxShadow=`inset 0 0 ${20+v*20}px rgba(0,180,216,${v*0.4})`;
    }}else if(g){{g.style.border='3px solid transparent';g.style.boxShadow='none';}}
    requestAnimationFrame(glowLoop);
  }}
  glowLoop();
}})();
</script>"""
    else:
        avatar = f"""
<canvas id="ccCanvas" width="260" height="280"
  style="border-radius:16px;background:linear-gradient(135deg,#001a4d,#002d80);
         box-shadow:0 0 30px rgba(0,180,216,0.3);display:block;margin:0 auto"></canvas>
<script>{CC_CANVAS_JS}</script>"""

    return f"""
<div id="cc-widget" style="width:100%;font-family:'Noto Sans SC',sans-serif">
<div style="text-align:center;margin-bottom:16px">{avatar}</div>
<div id="ccStatus" style="text-align:center;font-size:13px;color:#00B4D8;margin-bottom:12px;min-height:20px">⏸ 待机中</div>
<div id="ccSubtitle" style="min-height:60px;background:rgba(0,56,147,0.08);border:1px solid rgba(0,180,216,0.2);
     border-radius:10px;padding:12px 16px;font-size:14px;color:#0A1628;line-height:1.7;margin-bottom:12px"></div>
<div style="display:flex;gap:8px;justify-content:center;margin-bottom:12px">
  <button onclick="pauseResumeSpeech()" id="btnPause"
    style="padding:8px 18px;border:none;border-radius:8px;background:#003893;color:white;cursor:pointer;font-size:13px;font-weight:600">⏸ 暂停</button>
  <button onclick="replaySpeech()"
    style="padding:8px 18px;border:none;border-radius:8px;background:#00B4D8;color:white;cursor:pointer;font-size:13px;font-weight:600">🔁 重播</button>
  <button onclick="stopSpeech()"
    style="padding:8px 18px;border:none;border-radius:8px;background:#eee;color:#333;cursor:pointer;font-size:13px;font-weight:600">⏹ 停止</button>
</div>
<div style="text-align:center">
  <label style="font-size:13px;color:#4A6080;margin-right:8px">语言：</label>
  <select id="langSelect" style="padding:4px 12px;border-radius:6px;border:1px solid #C8D8F5;font-size:13px;color:#003893">
    <option value="zh-CN">中文</option><option value="en-US">English</option>
  </select>
</div>
<script>{SPEECH_JS}</script>
</div>"""


def _init_p2_state():
    defaults = {
        "p2_messages": [], "p2_lang": "zh-CN",
        "p2_knowledge": DEFAULT_KNOWLEDGE,
        "p2_last_answer": "", "p2_custom_avatar_b64": None,
        "p2_voice": "alloy"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _ask_glm(question, knowledge, lang, history):
    from openai import OpenAI
    from modules.config import OPENAI_API_KEY, OPENAI_BASE_URL
    lang_instr = "请用中文回答。" if lang == "zh-CN" else "Please answer in English."
    sys_prompt = f"""你是深圳技术大学的智能实验助手「创创」，专门解答迈克尔逊干涉法测金属杨氏模量实验相关问题。
{lang_instr}
回答要求：准确简洁专业，涉及公式用LaTeX，不超过300字，给出具体可行的调试步骤。
参考知识库：{knowledge}"""
    messages = [{"role": "system", "content": sys_prompt}]
    for m in history[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30)
        resp = client.chat.completions.create(model="glm-4", messages=messages, max_tokens=512)
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ 智谱接口请求失败：{str(e)}"


def _get_zhipu_tts_b64(text, voice: str = "alloy"):
    try:
        import requests
        from modules.config import OPENAI_API_KEY
        r = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/audio/speech",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": "cogview-speech", "input": text, "voice": voice, "response_format": "mp3"},
            timeout=10
        )
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except Exception:
        pass
    return None


def _trigger_speech(text, lang):
    """R002+R005: 先停止旧语音，再触发新语音"""
    safe = re.sub(r'\$[^$]+\$|\\\([^)]+\\\)', '', text)
    safe = re.sub(r'[`\\]', ' ', safe).replace('\n', ' ').strip()[:300]
    safe_js = safe.replace('`', "'").replace('"', '\\"')

    voice = st.session_state.get("p2_voice", "alloy")
    tts_b64 = _get_zhipu_tts_b64(safe, voice=voice)
    if tts_b64:
        st.components.v1.html(f"""<script>
(function(){{
  const frames=window.parent.document.querySelectorAll('iframe');
  frames.forEach(f=>{{try{{f.contentWindow.postMessage({{type:'cc_speak_b64',b64:"{tts_b64}",text:`{safe_js}`}},'*');}}catch(e){{}}}}); 
}})();
</script>""", height=0)
    else:
        st.components.v1.html(f"""<script>
(function(){{
  const frames=window.parent.document.querySelectorAll('iframe');
  frames.forEach(f=>{{try{{f.contentWindow.postMessage({{type:'cc_speak_fallback',text:`{safe_js}`,lang:'{lang}'}},'*');}}catch(e){{}}}}); 
  // 同帧兜底
  if(window.speechSynthesis){{window.speechSynthesis.cancel();setTimeout(()=>{{const u=new SpeechSynthesisUtterance(`{safe_js}`);u.lang='{lang}';u.rate=0.9;window.speechSynthesis.speak(u);}},150);}}
}})();
</script>""", height=0)


def render_p2():
    _init_p2_state()

    st.markdown("""<div class="sztu-card">
        <div class="sztu-card-title" style="font-size:20px">🤖 「创创」动态卡通语音交互智能体
        <span style="font-size:12px;font-weight:400;color:#4A6080;margin-left:12px">P2 · 智谱AI · v4.0</span>
        </div></div>""", unsafe_allow_html=True)

    col_avatar, col_chat = st.columns([1, 1.6], gap="large")

    with col_avatar:
        st.markdown('<div class="sztu-card-title">🎭 创创</div>', unsafe_allow_html=True)
        avatar_html = _build_avatar_html(st.session_state.p2_custom_avatar_b64)
        st.components.v1.html(avatar_html, height=420, scrolling=False)

        # R004: 自定义吉祥物
        with st.expander("🖼 自定义吉祥物形象", expanded=False):
            st.caption("上传 JPG/PNG 图片替换默认创创形象")
            uploaded_img = st.file_uploader("上传图片", type=["jpg","jpeg","png"],
                                            key="p2_avatar_upload", label_visibility="collapsed")
            c_u1, c_u2 = st.columns(2)
            if uploaded_img and c_u1.button("✅ 应用", use_container_width=True):
                st.session_state.p2_custom_avatar_b64 = base64.b64encode(uploaded_img.read()).decode()
                st.rerun()
            if c_u2.button("🔄 恢复默认", use_container_width=True, key="rst_avatar"):
                st.session_state.p2_custom_avatar_b64 = None
                st.rerun()

        lang_opt = st.radio("交互语言", ["🇨🇳 中文", "🇺🇸 English"], horizontal=True, key="p2_lang_radio")
        st.session_state.p2_lang = "zh-CN" if "中文" in lang_opt else "en-US"
        voice_map = {
            "alloy（通用）": "alloy",
            "echo（沉稳）": "echo",
            "fable（叙述）": "fable",
            "onyx（低沉）": "onyx",
            "nova（明亮）": "nova",
            "shimmer（柔和）": "shimmer",
        }
        selected_voice_label = next(
            (k for k, v in voice_map.items() if v == st.session_state.p2_voice),
            "alloy（通用）",
        )
        selected_voice_label = st.selectbox(
            "语音音色",
            options=list(voice_map.keys()),
            index=list(voice_map.keys()).index(selected_voice_label),
            key="p2_voice_select",
            help="切换创创语音播放时的音色",
        )
        st.session_state.p2_voice = voice_map[selected_voice_label]

        st.markdown('<div class="sztu-card-title" style="margin-top:16px">💡 快捷提问</div>', unsafe_allow_html=True)
        qs_zh = ["干涉环出现椭圆怎么调？","杨氏模量公式推导过程？","A类不确定度怎么计算？","测量直径为何要多次？","如何消除空程误差？"]
        qs_en = ["Why are interference fringes elliptical?","How to derive Young's modulus formula?","How to calculate Type-A uncertainty?"]
        qs = qs_zh if st.session_state.p2_lang == "zh-CN" else qs_en
        for q in qs:
            if st.button(q, use_container_width=True, key=f"quick_{q[:10]}"):
                st.session_state._p2_pending_question = q
                st.rerun()

    with col_chat:
        st.markdown('<div class="sztu-card-title">💬 对话记录</div>', unsafe_allow_html=True)
        chat_box = st.container(height=340)
        with chat_box:
            if not st.session_state.p2_messages:
                st.markdown("""<div style="text-align:center;padding:40px;color:#4A6080">
                    <div style="font-size:36px;margin-bottom:12px">👋</div>
                    <div>你好！我是创创，深技大实验助手。<br>有任何实验问题都可以问我～</div>
                </div>""", unsafe_allow_html=True)
            else:
                for msg in st.session_state.p2_messages:
                    if msg["role"] == "user":
                        st.markdown(f"""<div style="text-align:right;margin:8px 0">
                          <span style="background:#003893;color:white;padding:8px 14px;
                                border-radius:16px 16px 4px 16px;font-size:14px;
                                display:inline-block;max-width:85%">{msg["content"]}</span></div>""",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div style="text-align:left;margin:8px 0">
                          <span style="background:#F0F4FF;color:#0A1628;padding:8px 14px;
                                border:1px solid #C8D8F5;border-radius:16px 16px 16px 4px;
                                font-size:14px;display:inline-block;max-width:85%;line-height:1.7">{msg["content"]}</span></div>""",
                                    unsafe_allow_html=True)

        user_input = st.text_input("输入问题", placeholder="例：干涉环吞入和吐出如何区分？",
                                   key="p2_input", label_visibility="collapsed")
        c1, c2, c3 = st.columns([2,1,1])
        send_btn   = c1.button("📨 发送提问", type="primary", use_container_width=True)
        clear_btn  = c2.button("🗑 清空记录", use_container_width=True)
        replay_btn = c3.button("🔁 重播语音", use_container_width=True)

        pending  = st.session_state.pop("_p2_pending_question", None)
        question = pending or (user_input if send_btn else None)

        if clear_btn:
            # R005: 清空时停止语音
            st.components.v1.html("<script>const f=window.parent.document.querySelectorAll('iframe');f.forEach(x=>{try{x.contentWindow.postMessage({type:'cc_stop'},'*');}catch(e){}});</script>", height=0)
            st.session_state.p2_messages = []
            st.session_state.p2_last_answer = ""
            st.rerun()

        if replay_btn and st.session_state.p2_last_answer:
            _trigger_speech(st.session_state.p2_last_answer, st.session_state.p2_lang)

        if question:
            st.session_state.p2_messages.append({"role":"user","content":question})
            with st.spinner("创创正在思考..."):
                answer = _ask_glm(question, st.session_state.p2_knowledge,
                                  st.session_state.p2_lang, st.session_state.p2_messages[:-1])
            st.session_state.p2_messages.append({"role":"assistant","content":answer})
            st.session_state.p2_last_answer = answer
            _trigger_speech(answer, st.session_state.p2_lang)
            st.rerun()

        st.markdown("---")
        with st.expander("📚 自定义知识库管理", expanded=False):
            st.markdown("在此编辑知识库内容，修改后实时生效。")
            kb = st.text_area("知识库", value=st.session_state.p2_knowledge, height=250, key="p2_kb_editor")
            kc1, kc2 = st.columns(2)
            if kc1.button("💾 保存知识库", use_container_width=True):
                st.session_state.p2_knowledge = kb
                st.success("✅ 已保存")
            if kc2.button("🔄 恢复默认", use_container_width=True):
                st.session_state.p2_knowledge = DEFAULT_KNOWLEDGE
                st.rerun()
