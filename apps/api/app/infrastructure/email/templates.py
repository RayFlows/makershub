# app/infrastructure/email/templates.py
"""
邮件内容模板

本文件只负责把验证码发送请求转换成邮件客户端可以理解的 MIME 消息。
业务层仍然决定验证码用途、有效期、频率限制和消费规则；SMTP 适配器只负责投递。
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr
from html import escape

# --- 验证码邮件 ---


def build_email_verification_message(
    *,
    email: str,
    purpose: str,
    code: str,
    expires_minutes: int,
    from_email: str,
    from_name: str,
    home_url: str = "https://scumaker.com",
    brand_image_url: str | None = None,
) -> EmailMessage:
    """构建带 HTML 样式和纯文本兜底的验证码邮件。"""

    purpose_label = describe_email_verification_purpose(purpose)
    message = EmailMessage()
    message["Subject"] = "MakersHub 邮箱验证码"
    message["From"] = formataddr((from_name, from_email))
    message["To"] = email
    message.set_content(
        build_email_verification_text(
            purpose_label=purpose_label,
            code=code,
            expires_minutes=expires_minutes,
            home_url=home_url,
        )
    )
    message.add_alternative(
        build_email_verification_html(
            purpose_label=purpose_label,
            code=code,
            expires_minutes=expires_minutes,
            home_url=home_url,
            brand_image_url=brand_image_url,
        ),
        subtype="html",
    )

    return message


def build_email_verification_text(
    *,
    purpose_label: str,
    code: str,
    expires_minutes: int,
    home_url: str,
) -> str:
    """构建纯文本邮件内容，供不显示 HTML 的邮件客户端兜底。"""

    return "\n".join(
        [
            "你的 MakersHub 邮箱验证码如下：",
            "",
            code,
            "",
            f"验证码用途：{purpose_label}",
            f"有效期：{expires_minutes} 分钟",
            "",
            "请回到当前页面输入验证码完成操作。",
            f"MakersHub 首页：{home_url}",
            "如果不是你本人操作，请忽略这封邮件。",
        ]
    )


def build_email_verification_html(
    *,
    purpose_label: str,
    code: str,
    expires_minutes: int,
    home_url: str,
    brand_image_url: str | None,
) -> str:
    """构建适合主流邮箱客户端展示的 HTML 邮件内容。"""

    safe_purpose_label = escape(purpose_label)
    safe_code = escape(code)
    safe_expires_minutes = escape(str(expires_minutes))
    brand_header = build_brand_header_html(home_url=home_url, brand_image_url=brand_image_url)

    return f"""<!doctype html>
<html lang="zh-CN" style="background:#fffffe;background-color:#fffffe;
  background-image:linear-gradient(#fffffe,#fffffe);">
  <head>
    <meta name="color-scheme" content="light only">
    <meta name="supported-color-schemes" content="light only">
  </head>
  <body bgcolor="#fffffe" style="margin:0;padding:0;background:#fffffe;background-color:#fffffe;
    background-image:linear-gradient(#fffffe,#fffffe);
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',Arial,sans-serif;
    color:#172033 !important;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#fffffe"
      style="border-collapse:collapse;background:#fffffe;background-color:#fffffe;
      background-image:linear-gradient(#fffffe,#fffffe);">
      <tr>
        <td align="center" style="padding:32px 16px;">
          <table role="presentation" width="650" cellspacing="0" cellpadding="0" bgcolor="#fffffe"
            style="width:100%;max-width:650px;border-collapse:collapse;background:#fffffe;
            background-color:#fffffe;background-image:linear-gradient(#fffffe,#fffffe);">
            <tr>
              <td style="height:8px;background:#00ADB5;font-size:0;line-height:0;">&nbsp;</td>
            </tr>
            <tr>
              <td bgcolor="#fffffe" style="padding:36px 40px 40px 40px;background:#fffffe;
                background-color:#fffffe;background-image:linear-gradient(#fffffe,#fffffe);">
                <table role="presentation" cellspacing="0" cellpadding="0"
                  style="border-collapse:collapse;margin-bottom:34px;">
                  <tr>
                    <td style="vertical-align:middle;">{brand_header}</td>
                  </tr>
                </table>

                <h1 style="margin:0 0 24px 0;font-size:20px;line-height:30px;font-weight:800;
                  color:#101828 !important;">您的 MakersHub 验证码</h1>
                <p style="margin:0 0 18px 0;font-size:15px;line-height:24px;color:#344054 !important;">
                  请在当前页面输入以下 6 位验证码，完成{safe_purpose_label}。</p>
                <div style="margin:0 0 22px 0;font-size:34px;line-height:42px;font-weight:700;
                  letter-spacing:4px;color:#101828 !important;">{safe_code}</div>
                <p style="margin:0 0 28px 0;font-size:14px;line-height:22px;color:#344054 !important;">
                  此验证码将在 <strong>{safe_expires_minutes} 分钟</strong> 后失效；如果您重新申请了验证码，
                  请使用最新一封邮件中的验证码。</p>

                <p style="margin:0;font-size:14px;line-height:22px;color:#475467 !important;">
                  如果不是您本人操作，请忽略这封邮件。SCUMaker 工作人员不会向您索要验证码。
                </p>
              </td>
            </tr>
          </table>
          <div style="padding:22px 12px 0 12px;font-size:12px;line-height:20px;
            color:#98a2b3 !important;text-align:center;">
            MakersHub · scumaker.com
          </div>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def build_brand_header_html(*, home_url: str, brand_image_url: str | None) -> str:
    """构建邮件品牌头；配置图片时图片本身作为官网链接。"""

    safe_home_url = escape(home_url.strip() or "https://scumaker.com", quote=True)
    if brand_image_url:
        safe_brand_image_url = escape(brand_image_url.strip(), quote=True)
        return f"""<a href="{safe_home_url}" target="_blank"
                        style="display:inline-block;text-decoration:none;background:#fffffe;
                        background-color:#fffffe;padding:2px 0;">
                        <img src="{safe_brand_image_url}" width="300" alt="SCUMAKER"
                          style="display:block;width:300px;max-width:100%;height:auto;border:0;
                          outline:none;text-decoration:none;background:#fffffe;background-color:#fffffe;">
                      </a>"""

    return f"""<a href="{safe_home_url}" target="_blank"
                  style="display:inline-block;text-decoration:none;color:#101828;background:#fffffe;
                  background-color:#fffffe;">
                  <span style="display:block;font-size:22px;font-weight:800;letter-spacing:1px;">
                    SCUMAKER
                  </span>
                  <span style="display:block;font-size:13px;line-height:20px;color:#667085;">
                    MakersHub
                  </span>
                </a>"""


def describe_email_verification_purpose(purpose: str) -> str:
    """把验证码用途转换成用户能理解的文案。"""

    labels = {
        "bind_email": "绑定邮箱",
        "first_login": "网页端首次登录",
    }
    return labels.get(purpose.strip().lower(), purpose.strip())
