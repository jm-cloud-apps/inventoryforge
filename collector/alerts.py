"""Push alerts when a watched item flips to in-stock. Discord webhook + optional email."""
import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText


def _line(it):
    price = f" — ${it['price']:.2f}" if it.get("price") is not None else ""
    return f"**{it['title']}**{price}\n{it['retailer']} · {it['store']}\n{it.get('url', '')}"


def send_discord(webhook, restocks):
    if not webhook or not restocks:
        return
    content = "🔔 **Restock detected**\n\n" + "\n\n".join(_line(i) for i in restocks)
    body = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(
        webhook, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print(f"[alerts] sent Discord alert for {len(restocks)} item(s)")
    except Exception as e:
        print(f"[alerts] Discord failed: {e}")


def send_email(restocks):
    if os.getenv("EMAIL_ENABLED", "false").lower() != "true" or not restocks:
        return
    host, port = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))
    user, pw = os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
    to = os.getenv("EMAIL_TO")
    if not (host and user and pw and to):
        print("[alerts] email enabled but SMTP_* / EMAIL_TO incomplete")
        return
    text = "\n\n".join(_line(i).replace("**", "") for i in restocks)
    msg = MIMEText(text)
    msg["Subject"] = f"🔔 {len(restocks)} Pokémon restock(s)"
    msg["From"], msg["To"] = user, to
    try:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
        print(f"[alerts] sent email for {len(restocks)} item(s)")
    except Exception as e:
        print(f"[alerts] email failed: {e}")


def notify(restocks):
    send_discord(os.getenv("DISCORD_WEBHOOK_URL"), restocks)
    send_email(restocks)
