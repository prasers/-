"""
modules/qr_util.py
R001: 局域网访问二维码生成工具
纯JS实现，无需额外Python包，自动检测本机局域网IP
"""

import os
import socket
import uuid
from html import escape
import streamlit as st
import streamlit.components.v1 as components


def get_local_ip() -> str:
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def render_qr_banner(port: int = 8501):
    """
    在页面顶部渲染局域网访问二维码横幅
    使用纯JS Canvas绘制QR码，无需qrcode库
    """
    ip = get_local_ip()
    local_url = f"http://{ip}:{port}"
    public_url = os.getenv("PUBLIC_BASE_URL", "").strip()
    active_url = public_url or local_url
    safe_local_url = escape(local_url)
    safe_active_url = escape(active_url)
    uid = f"qr_{uuid.uuid4().hex[:8]}"

    # 使用 qrcode.js CDN 生成二维码
    qr_html = f"""
<div id="{uid}-banner" style="
    background: linear-gradient(135deg, #001a4d 0%, #002d80 100%);
    border: 1px solid rgba(0,180,216,0.4);
    border-radius: 12px;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 16px;
    box-shadow: 0 0 20px rgba(0,180,216,0.2);
    position: relative;
">
  <div id="{uid}-qrcode-container" style="flex-shrink:0; cursor:pointer" title="点击放大"></div>
  <div style="flex:1">
    <div style="color:#00B4D8;font-size:11px;letter-spacing:2px;font-family:monospace;margin-bottom:4px">
      📡 扫码访问地址
    </div>
    <div style="color:white;font-size:15px;font-weight:700;font-family:monospace;margin-bottom:6px">
      {safe_active_url}
    </div>
    <div style="color:rgba(255,255,255,0.5);font-size:11px">
      {('🌐 公网模式：外网可访问（PUBLIC_BASE_URL）' if public_url else '📶 局域网模式：同 WiFi 设备可访问')}
    </div>
    <div style="color:rgba(255,255,255,0.42);font-size:10px;margin-top:4px">
      本机地址：{safe_local_url}
    </div>
  </div>
  <button id="{uid}-zoom-btn"
    style="flex-shrink:0;background:rgba(0,180,216,0.2);border:1px solid rgba(0,180,216,0.4);
           color:#00B4D8;padding:6px 14px;border-radius:8px;cursor:pointer;font-size:12px;
           font-family:monospace">
    🔍 放大
  </button>
</div>

<!-- 放大弹窗 -->
<div id="{uid}-qr-modal" style="
    display:none;position:fixed;top:0;left:0;width:100%;height:100%;
    background:rgba(0,0,0,0.7);z-index:9999;
    justify-content:center;align-items:center;cursor:pointer
">
  <div style="background:#001a4d;border:2px solid #00B4D8;border-radius:16px;
              padding:32px;text-align:center;box-shadow:0 0 40px rgba(0,180,216,0.5)"
       id="{uid}-modal-card">
    <div id="{uid}-qrcode-large"></div>
    <div style="color:#00B4D8;margin-top:16px;font-family:monospace;font-size:14px">{safe_active_url}</div>
    <div style="color:rgba(255,255,255,0.5);margin-top:8px;font-size:12px">点击外部关闭</div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
(function() {{
  const url = "{safe_active_url}";
  const small = document.getElementById("{uid}-qrcode-container");
  const large = document.getElementById("{uid}-qrcode-large");
  const modal = document.getElementById("{uid}-qr-modal");
  const zoomBtn = document.getElementById("{uid}-zoom-btn");
  const modalCard = document.getElementById("{uid}-modal-card");

  function toggleQRModal() {{
    if (!modal) return;
    modal.style.display = (modal.style.display === "flex") ? "none" : "flex";
  }}
  if (zoomBtn) zoomBtn.addEventListener("click", toggleQRModal);
  if (small) small.addEventListener("click", toggleQRModal);
  if (modal) modal.addEventListener("click", toggleQRModal);
  if (modalCard) modalCard.addEventListener("click", (e) => e.stopPropagation());

  // 小二维码（横幅内）
  new QRCode(small, {{
    text: url,
    width: 92,
    height: 92,
    colorDark: "#001a4d",
    colorLight: "#FFFFFF",
    correctLevel: QRCode.CorrectLevel.H
  }});

  // 大二维码（弹窗内）
  new QRCode(large, {{
    text: url,
    width: 280,
    height: 280,
    colorDark: "#001a4d",
    colorLight: "#FFFFFF",
    correctLevel: QRCode.CorrectLevel.H
  }});
}})();
</script>
"""
    components.html(qr_html, height=130, scrolling=False)
