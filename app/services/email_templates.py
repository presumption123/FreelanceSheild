"""Parameterized escalation email templates."""

from dataclasses import dataclass


@dataclass
class EmailTemplate:
    subject: str
    html_body: str
    text_body: str


def _html_wrapper(body: str) -> str:
    return f"""<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:24px;">{body}
<hr style="margin-top:32px;border:none;border-top:1px solid #eee;"/>
<p style="font-size:12px;color:#888;">Sent via FreelanceShield on behalf of the freelancer.</p>
</div></body></html>"""


def reminder_1_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    amount: str,
    days_overdue: int,
    due_date: str,
    portal_url: str,
) -> EmailTemplate:
    days_text = f"{days_overdue} day{'s' if days_overdue != 1 else ''}"
    text = f"""Hi {client_name},

I hope you're doing well. I wanted to send a quick note that invoice {invoice_number} for {amount} was due on {due_date} ({days_text} ago).

If you've already sent payment, please disregard this message. If not, you can view the invoice and pay securely here:
{portal_url}

Please let me know if you have any questions.

Thank you,
{freelancer_name}"""
    html = _html_wrapper(
        f"<p>Hi {client_name},</p>"
        f"<p>I wanted to send a quick note that invoice <strong>{invoice_number}</strong> for <strong>{amount}</strong> "
        f"was due on {due_date} ({days_text} ago).</p>"
        f'<p><a href="{portal_url}">View invoice and pay</a></p>'
        f"<p>Thank you,<br/>{freelancer_name}</p>"
    )
    return EmailTemplate(subject=f"Invoice {invoice_number} — Payment reminder", html_body=html, text_body=text)


def reminder_2_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    amount: str,
    days_overdue: int,
    portal_url: str,
) -> EmailTemplate:
    text = f"""Hi {client_name},

This is a follow-up regarding invoice {invoice_number} for {amount}, which is now {days_overdue} days overdue.

Please arrange payment as soon as possible: {portal_url}

{freelancer_name}"""
    html = _html_wrapper(
        f"<p>Hi {client_name},</p>"
        f"<p>Invoice <strong>{invoice_number}</strong> for <strong>{amount}</strong> is now "
        f"<strong>{days_overdue} days overdue</strong>.</p>"
        f'<p><a href="{portal_url}">Pay now</a></p>'
    )
    return EmailTemplate(subject=f"Invoice {invoice_number} — {days_overdue} days overdue", html_body=html, text_body=text)


def reminder_3_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    amount: str,
    days_overdue: int,
    portal_url: str,
) -> EmailTemplate:
    text = f"""Hi {client_name},

Despite previous reminders, invoice {invoice_number} for {amount} remains unpaid ({days_overdue} days overdue). This is affecting our professional relationship.

Please pay immediately: {portal_url}

{freelancer_name}"""
    html = _html_wrapper(
        f"<p>Hi {client_name},</p>"
        f"<p>Despite previous reminders, invoice <strong>{invoice_number}</strong> remains unpaid "
        f"({days_overdue} days overdue). This is affecting our professional relationship.</p>"
        f'<p><a href="{portal_url}">Pay now</a></p>'
    )
    return EmailTemplate(
        subject=f"Invoice {invoice_number} — Immediate payment required",
        html_body=html,
        text_body=text,
    )


def demand_letter_email_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    amount: str,
    deadline: str,
    portal_url: str,
) -> EmailTemplate:
    text = f"""Dear {client_name},

Please find attached a formal demand for payment regarding invoice {invoice_number} for {amount}.

Payment is required by {deadline}. View details: {portal_url}

{freelancer_name}"""
    html = _html_wrapper(
        f"<p>Dear {client_name},</p>"
        f"<p>A formal demand for payment regarding invoice <strong>{invoice_number}</strong> "
        f"({amount}) has been issued. Payment is required by <strong>{deadline}</strong>.</p>"
        f'<p><a href="{portal_url}">View invoice</a></p>'
    )
    return EmailTemplate(
        subject=f"FORMAL DEMAND — Invoice {invoice_number}",
        html_body=html,
        text_body=text,
    )


def final_notice_email_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    amount: str,
    deadline: str,
    court_name: str,
    portal_url: str,
) -> EmailTemplate:
    text = f"""Dear {client_name},

FINAL NOTICE: Invoice {invoice_number} for {amount} must be paid by {deadline} or legal proceedings may be filed in {court_name}.

{portal_url}

{freelancer_name}"""
    html = _html_wrapper(
        f"<p><strong>FINAL NOTICE</strong></p>"
        f"<p>Invoice {invoice_number} ({amount}) must be paid by {deadline} "
        f"or legal proceedings may be filed in {court_name}.</p>"
    )
    return EmailTemplate(
        subject=f"FINAL NOTICE — Invoice {invoice_number}",
        html_body=html,
        text_body=text,
    )


def court_notice_email_template(
    freelancer_name: str,
    client_name: str,
    invoice_number: str,
    court_name: str,
) -> EmailTemplate:
    text = f"""Dear {client_name},

A small claims court packet has been prepared regarding unpaid invoice {invoice_number}. The claimant may file in {court_name}.

{freelancer_name}"""
    html = _html_wrapper(
        f"<p>A small claims court packet has been prepared for invoice <strong>{invoice_number}</strong>.</p>"
    )
    return EmailTemplate(
        subject=f"Court action prepared — Invoice {invoice_number}",
        html_body=html,
        text_body=text,
    )


TEMPLATE_MAP = {
    "reminder_1": reminder_1_template,
    "reminder_2": reminder_2_template,
    "reminder_3": reminder_3_template,
    "demand_letter": demand_letter_email_template,
    "final_notice": final_notice_email_template,
    "court_notice": court_notice_email_template,
}
