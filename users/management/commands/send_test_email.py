from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage, get_connection


class Command(BaseCommand):
    help = "Send a test email using current SMTP settings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="ismailnaser67@gmail.com",
            help="Recipient email address",
        )
        parser.add_argument(
            "--subject",
            default="Radar SMTP test",
            help="Email subject",
        )

    def handle(self, *args, **options):
        to_email = str(options["to"]).strip()
        subject = str(options["subject"]).strip()

        if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise SystemExit(
                "SMTP env vars missing. Set EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD (and optional DEFAULT_FROM_EMAIL)."
            )

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or settings.EMAIL_HOST_USER
        body = (
            "This is a test email from Radar.\n\n"
            f"Host: {settings.EMAIL_HOST}\n"
            f"Port: {settings.EMAIL_PORT}\n"
            f"TLS: {settings.EMAIL_USE_TLS}\n"
            f"From: {from_email}\n"
            f"To: {to_email}\n"
        )

        connection = get_connection(fail_silently=False)
        email = EmailMessage(subject=subject, body=body, from_email=from_email, to=[to_email], connection=connection)

        self.stdout.write("Connecting to SMTP and sending…")
        sent = email.send(fail_silently=False)
        if sent:
            self.stdout.write(self.style.SUCCESS(f"Sent OK to {to_email}"))
        else:
            raise SystemExit("Send failed (email.send returned 0).")

