"""Report engine: compiles the ExecutiveBrief into a styled PDF via ReportLab.

Ported from pdfrules.md: Letter pages, 36pt margins, slate/neutral palette,
keepWithNext headings, and a two-pass NumberedCanvas rendering "Page X of Y".
"""

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .logging_utils import get_logger
from .state import ExecutiveBrief

logger = get_logger("competepulse.reporting")

PALETTE = {
    "title": colors.HexColor("#1A202C"),
    "heading": colors.HexColor("#2D3748"),
    "body": colors.HexColor("#4A5568"),
    "muted": colors.HexColor("#718096"),
    "rule": colors.HexColor("#E2E8F0"),
    "table_header_bg": colors.HexColor("#EDF2F7"),
    "grid": colors.HexColor("#CBD5E0"),
}


class NumberedCanvas(pdfcanvas.Canvas):
    """Two-pass canvas that renders 'Page X of Y' footers after layout."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.pages: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 — ReportLab API name
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(PALETTE["muted"])
        footer_text = f"Competepulse Intelligence Brief  |  Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 36, 25, footer_text)
        self.setStrokeColor(PALETTE["rule"])
        self.setLineWidth(0.5)
        self.line(36, 40, letter[0] - 36, 40)
        self.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=22, leading=26, textColor=PALETTE["title"], spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=14, textColor=PALETTE["body"], spaceAfter=18,
        ),
        "heading": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=PALETTE["heading"],
            spaceBefore=14, spaceAfter=6, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "BodyDark", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=15, textColor=PALETTE["heading"], spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "BulletBody", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=14, textColor=PALETTE["body"],
            spaceAfter=5, leftIndent=12, bulletIndent=2,
        ),
        "muted": ParagraphStyle(
            "MutedNote", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=9, leading=13, textColor=PALETTE["muted"], spaceAfter=8,
        ),
    }


def _esc(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def build_story(analysis: ExecutiveBrief, domain: str, generated_at: datetime) -> list:
    styles = _styles()
    story: list = []

    story.append(Paragraph("Competepulse Weekly Intelligence Brief", styles["title"]))
    story.append(
        Paragraph(
            f"Target Domain: <b>{_esc(domain)}</b> &nbsp;|&nbsp; Week of "
            f"{generated_at.strftime('%B %d, %Y')} &nbsp;|&nbsp; "
            "Generated automatically via Vector Diff Analysis",
            styles["subtitle"],
        )
    )

    story.append(Paragraph("Executive Summary", styles["heading"]))
    story.append(Paragraph(_esc(analysis.executive_summary), styles["body"]))
    story.append(Spacer(1, 6))

    if analysis.pricing_shifts:
        story.append(Paragraph("1. Pricing & Packaging Shifts", styles["heading"]))
        table_rows = [["Tier", "Change Type", "Details"]]
        for shift in analysis.pricing_shifts:
            table_rows.append([_esc(shift.tier_name), _esc(shift.change_type), _esc(shift.details)])
        table = Table(table_rows, colWidths=[100, 110, 314], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PALETTE["table_header_bg"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), PALETTE["title"]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, PALETTE["grid"]),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))

    if analysis.product_launches:
        story.append(Paragraph("2. Product Launches & Feature Updates", styles["heading"]))
        for item in analysis.product_launches:
            story.append(Paragraph(_esc(item), styles["bullet"], bulletText="•"))
        story.append(Spacer(1, 4))

    if analysis.terms_updates:
        story.append(Paragraph("3. Terms of Service & Policy Changes", styles["heading"]))
        for item in analysis.terms_updates:
            story.append(Paragraph(_esc(item), styles["bullet"], bulletText="•"))
        story.append(Spacer(1, 4))

    if analysis.key_takeaways:
        story.append(Paragraph("Key Takeaways", styles["heading"]))
        for item in analysis.key_takeaways:
            story.append(Paragraph(_esc(item), styles["bullet"], bulletText="→"))

    if not (
        analysis.pricing_shifts or analysis.product_launches
        or analysis.terms_updates or analysis.key_takeaways
    ):
        story.append(
            Paragraph(
                "No significant competitive movements were detected this week.",
                styles["muted"],
            )
        )

    return story


def generate_executive_pdf(
    analysis: ExecutiveBrief,
    domain: str,
    output_dir: Path,
    generated_at: datetime | None = None,
) -> Path:
    """Compile the brief into reports/competepulse_brief_{domain}_{date}.pdf."""
    generated_at = generated_at or datetime.now(timezone.utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_domain = "".join(c if c.isalnum() or c in ".-" else "_" for c in domain)
    filename = f"competepulse_brief_{safe_domain}_{generated_at:%Y-%m-%d}.pdf"
    output_path = output_dir / filename

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=40,
        bottomMargin=50,
        title=f"Competepulse Brief — {domain}",
        author="Competepulse",
    )

    story = build_story(analysis, domain, generated_at)
    doc.build(story, canvasmaker=NumberedCanvas)
    logger.info("PDF compiled: %s", output_path)
    return output_path
