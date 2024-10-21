from flask_mail import Mail, Message
from config import Config

mail = Mail()

def init_mail(app):
    app.config['MAIL_SERVER'] = Config.MAIL_SERVER
    app.config['MAIL_PORT'] = Config.MAIL_PORT
    app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
    app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
    app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER
    mail.init_app(app)

def send_otp_email(to_email, otp):
    msg = Message("Your OTP Code", recipients=[to_email])
    msg.body = f"Your OTP code is {otp}. It will expire in 10 minutes."
    mail.send(msg)

def send_password_reset_email(to_email, reset_token):
    msg = Message("Password Reset Request", recipients=[to_email])
    reset_link = f"{Config.FRONTEND_URL}/reset-password?token={reset_token}"
    msg.body = f"To reset your password, click the following link: {reset_link}."
    mail.send(msg)
