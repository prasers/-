"""
utils/qr_generator.py
二维码生成工具（用于竞赛展示场景的手机扫码访问）
"""

import io
import base64
from typing import Optional


def generate_qr_bytes(url: str, size: int = 300) -> Optional[bytes]:
    """
    生成二维码图片字节流
    返回 PNG bytes 或 None（依赖缺失时）
    """
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont

        qr = qrcode.QRCode(
            version=3,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # 深技大蓝配色
        img = qr.make_image(
            fill_color="#003893",
            back_color="#F0F4FF"
        )
        img = img.resize((size, size), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        return None


def generate_qr_base64(url: str, size: int = 250) -> Optional[str]:
    """返回 base64 编码的二维码图片（用于 HTML 嵌入）"""
    b = generate_qr_bytes(url, size)
    if b:
        return base64.b64encode(b).decode()
    return None


def render_qr_html(url: str, title: str = "扫码访问") -> str:
    """生成可嵌入 Streamlit 的二维码 HTML 组件"""
    b64 = generate_qr_base64(url)
    if b64:
        return f"""
        <div style="text-align:center;padding:20px;background:#F0F4FF;
                    border:1px solid #C8D8F5;border-radius:12px">
            <img src="data:image/png;base64,{b64}" 
                 style="width:200px;height:200px;border-radius:8px"/>
            <div style="font-size:13px;color:#003893;font-weight:600;margin-top:10px">
                {title}
            </div>
            <div style="font-size:11px;color:#4A6080;margin-top:4px;word-break:break-all">
                {url}
            </div>
        </div>
        """
    else:
        return f"""
        <div style="text-align:center;padding:20px;background:#F0F4FF;
                    border:1px solid #C8D8F5;border-radius:12px">
            <div style="font-size:13px;color:#003893">{title}</div>
            <div style="font-size:12px;color:#4A6080;margin-top:8px;word-break:break-all">
                🔗 {url}
            </div>
            <div style="font-size:11px;color:#aaa;margin-top:6px">
                （安装 qrcode[pil] 以显示二维码）
            </div>
        </div>
        """
