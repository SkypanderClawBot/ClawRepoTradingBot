import smtplib
from email.mime.text import MIMEText
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('skypanderclawbot@gmail.com', 'cdvdxfuyopsglroq')
msg = MIMEText('**Test #3 - Pure Python SMTP von Botti!**\\n\\nGesendet: ' + __import__('time').strftime('%Y-%m-%d %H:%M Berlin'))
msg['Subject'] = 'Botti SMTP Test #3 - Python SUCCESS'
msg['From'] = 'skypanderclawbot@gmail.com'
msg['To'] = 'skypanderclawbot@gmail.com'
server.send_message(msg)
server.quit()
print('SMTP Test #3 gesendet! ✅ Check Gmail in 30s.')
