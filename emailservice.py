from flask_mail import Mail, Message
from config import Config
from flask import render_template_string

mail = Mail()

# Initialize mail configuration
def init_mail(app):
    app.config['MAIL_SERVER'] = Config.MAIL_SERVER
    app.config['MAIL_PORT'] = Config.MAIL_PORT
    app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
    app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
    app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER
    mail.init_app(app)

# Send OTP email
def send_otp_email(to_email, otp):
    msg = Message("Your OTP Code", recipients=[to_email])
    msg.html = render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your OTP Code</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8f9fa; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td style="padding: 40px 20px; text-align: center; background-color: #000000;">
                                <h1 style="color: #ffffff; font-size: 28px; margin: 0;">Zyke</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 20px;">
                                <h2 style="color: #333; font-size: 24px; margin-bottom: 20px; text-align: center;">Your OTP Code</h2>
                                <p style="font-size: 16px; margin-bottom: 30px; text-align: center;">Use the following OTP to complete your action:</p>
                                <div style="background-color: #f8f9fa; color: #333; font-size: 32px; font-weight: bold; text-align: center; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                                    {{ otp }}
                                </div>
                                <p style="text-align: center; color: #666; font-size: 14px;">This code will expire in 5 minutes.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 14px; color: #666;">
                                <p>&copy; 2024 Zyke. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """, otp=otp)
    mail.send(msg)

# Send password reset email
def send_password_reset_email(to_email, reset_token):
    msg = Message("Password Reset Request", recipients=[to_email])
    reset_link = f"{Config.FRONTEND_URL}/reset-password?token={reset_token}"
    msg.html = render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset Request</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8f9fa; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td style="padding: 40px 20px; text-align: center; background-color: #000000;">
                                <h1 style="color: #ffffff; font-size: 28px; margin: 0;">Zyke</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 20px;">
                                <h2 style="color: #333; font-size: 24px; margin-bottom: 20px; text-align: center;">Password Reset Request</h2>
                                <p style="font-size: 16px; margin-bottom: 30px; text-align: center;">To reset your password, click the button below:</p>
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center">
                                            <a href="{{ reset_link }}" style="display: inline-block; padding: 12px 24px; background-color: #000000; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 4px;">Reset Password</a>
                                        </td>
                                    </tr>
                                </table>
                                <p style="margin-top: 30px; text-align: center; color: #666; font-size: 14px;">If you didn't request a password reset, please ignore this email.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 14px; color: #666;">
                                <p>&copy; 2024 Zyke. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """, reset_link=reset_link)
    mail.send(msg)

# Send confirmation email after successful registration
def send_confirmation_email(to_email):
    msg = Message("Welcome to Zyke!", recipients=[to_email])
    msg.html = render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome to Zyke</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8f9fa; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td style="padding: 40px 20px; text-align: center; background-color: #000000;">
                                <h1 style="color: #ffffff; font-size: 28px; margin: 0;">Zyke</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 20px;">
                                <h2 style="color: #333; font-size: 24px; margin-bottom: 20px; text-align: center;">Welcome to Zyke</h2>
                                <p style="font-size: 16px; margin-bottom: 30px; text-align: center;">We are thrilled to have you with us. Your registration is now complete.</p>
                                <p style="text-align: center; color: #666; font-size: 14px;">If you have any questions, feel free to contact our support team.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 14px; color: #666;">
                                <p>&copy; 2024 Zyke. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """)
    mail.send(msg)

# Send confirmation email after successful password reset
def send_password_reset_success_email(to_email):
    msg = Message("Password Reset Successful", recipients=[to_email])
    msg.html = render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset Successful</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8f9fa; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td style="padding: 40px 20px; text-align: center; background-color: #000000;">
                                <h1 style="color: #ffffff; font-size: 28px; margin: 0;">Zyke</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 20px;">
                                <h2 style="color: #333; font-size: 24px; margin-bottom: 20px; text-align: center;">Password Reset Successful</h2>
                                <p style="font-size: 16px; margin-bottom: 30px; text-align: center;">Your password has been successfully reset. If you did not initiate this change, please contact us immediately.</p>
                                <p style="text-align: center; color: #666; font-size: 14px;">If you have any questions, feel free to contact our support team.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 14px; color: #666;">
                                <p>&copy; 2024 Zyke. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """)
    mail.send(msg)
