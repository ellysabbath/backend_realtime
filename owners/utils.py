"""
Utilities for generating the treaty PDF from a garage registration record.
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


def generate_treaty_pdf(garage: dict, owner: dict = None) -> bytes:
    """
    Generate a treaty PDF from a garage record.
    - garage: dict with keys like name, address, email, primaryPhone, ...
    - owner: optional dict with owner information (fullName, phone, etc.)
    Returns the raw PDF as bytes.
    """
    owner = owner or {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"tApp Treaty — {garage.get('name', 'Garage')}",
        author="tApp",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e40af"),
        spaceBefore=16,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "body",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1f2937"),
    )
    small = ParagraphStyle(
        "small",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#6b7280"),
    )

    story = []

    # ── Header ──
    story.append(Paragraph("tApp — Garage Owner Treaty", h1))
    story.append(
        Paragraph(
            f"Agreement Reference: <b>TRT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</b>",
            small,
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "This agreement is entered into between <b>tApp</b> (\"the Platform\") and "
            f"<b>{garage.get('ownerName', owner.get('fullName', 'the Owner'))}</b> "
            f"of <b>{garage.get('name', '—')}</b> (\"the Owner\").",
            body,
        )
    )

    # ── Owner Information ──
    story.append(Paragraph("1. Owner Information", h2))
    owner_rows = [
        ["Owner Full Name", garage.get("ownerName") or owner.get("fullName") or "—"],
        ["Phone Number", owner.get("phone", "—")],
        ["Email Address", garage.get("email", "—")],
        ["Address", garage.get("address", "—")],
    ]
    owner_table = Table(owner_rows, colWidths=[5 * cm, 12 * cm])
    owner_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(owner_table)

    # ── Garage Information ──
    story.append(Paragraph("2. Garage Information", h2))
    garage_rows = [
        ["Garage Name", garage.get("name", "—")],
        ["Physical Address", garage.get("address", "—")],
        ["Email", garage.get("email", "—")],
        ["Primary Phone", garage.get("primaryPhone", "—")],
        ["Secondary Phone", garage.get("secondaryPhone", "—")],
    ]
    garage_table = Table(garage_rows, colWidths=[5 * cm, 12 * cm])
    garage_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#166534")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(garage_table)

    # ── Terms ──
    story.append(Paragraph("3. Terms and Conditions", h2))
    terms = [
        "The Owner agrees to provide vehicle repair and technical assistance services through the tApp platform.",
        "The Owner will pay a one-time activation fee of <b>50,000 TZS</b> to activate the garage account.",
        "The Owner agrees to assign only verified technicians who meet the platform's certification requirements.",
        "The Owner accepts responsibility for the accuracy of all information submitted during registration.",
        "The Platform reserves the right to suspend the garage account for violation of policies.",
        "This agreement is governed by the laws of the United Republic of Tanzania.",
    ]
    for i, term in enumerate(terms, start=1):
        story.append(Paragraph(f"{i}. {term}", body))
        story.append(Spacer(1, 4))

    # ── Payment Confirmation ──
    story.append(Paragraph("4. Activation Fee Confirmation", h2))
    story.append(
        Paragraph(
            "The Owner agrees to pay the activation fee of <b>50,000 TZS</b> via M-PESA, "
            "Airtel Money, or cash as recorded in the tApp platform.",
            body,
        )
    )

    # ── Signature ──
    story.append(PageBreak())
    story.append(Paragraph("5. Signatures", h2))
    story.append(Spacer(1, 24))

    sig_rows = [
        ["Owner Signature", "____________________________"],
        ["Owner Name", garage.get("ownerName") or owner.get("fullName") or "—"],
        ["Date", datetime.utcnow().strftime("%Y-%m-%d")],
        ["", ""],
        ["tApp Representative", "____________________________"],
        ["Date", datetime.utcnow().strftime("%Y-%m-%d")],
    ]
    sig_table = Table(sig_rows, colWidths=[5 * cm, 12 * cm])
    sig_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(sig_table)

    story.append(Spacer(1, 30))
    story.append(
        Paragraph(
            "This document was generated electronically by tApp and is valid without a "
            "physical seal once the Owner's signature is provided.",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()