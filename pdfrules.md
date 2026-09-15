# Technical Documentation: Programmatic PDF Brief Generation Engine (`Competepulse`)

## 1. Overview & Objectives

The **Programmatic PDF Brief Generation Engine** is the final execution layer of **Competepulse**. Its primary objective is to transform raw, unstructured LLM intelligence (pricing shifts, product updates, and policy changes) into a publication-ready, professional executive document.

  

Rather than relying on clunky word processors or brittle HTML-to-PDF print drivers, this module utilizes **ReportLab**to build documents programmatically via Python, ensuring deterministic layouts, clean typography, and strict adherence to enterprise design standards.

  

## 2. Core Architectural Principles

- **Declarative Document Storyline:** The PDF engine treats a document as a continuous "story" array of flowable elements (paragraphs, spacers, tables) rather than relying on absolute coordinate mapping.
    
      
    
- **Deterministic Pagination:** Page flows, breaks, and headers/footers are managed dynamically based on content volume, preventing text clipping or awkward page splits.
    
      
    
- **Strict Separation of Concerns:** Styling definitions (`ParagraphStyle`) are completely isolated from content generation logic to maintain consistent branding and typography across every weekly brief.
    
      
    

## 3. Tech Stack & Dependencies

- **Core Engine:** `reportlab` (specifically `SimpleDocTemplate`, `Paragraph`, `Spacer`, and `Table`)
    
      
    
- **Styling & Metrics:** `reportlab.lib.pagesizes` (Letter) and `reportlab.lib.styles` (`getSampleStyleSheet`)
    
      
    
- **Color Spaces:** `reportlab.lib.colors` (for Hex-based professional palette management)
    

## 4. Step-by-Step Implementation Flow

```
[Structured LLM JSON / Markdown Summary]
                   │
                   ▼
[Initialize Document Template (Letter Size & Margins)]
                   │
                   ▼
[Build Typography & Stylesheet (Custom Hierarchy)]
                   │
                   ▼
[Assemble Story Flow: Header ──► Spacer ──► Data Tables ──► Bullet Points]
                   │
                   ▼
[Canvas Callback: Dynamic Running Footers & Page Numbers]
                   │
                   ▼
[Compile & Output Final PDF (`executive_brief.pdf`)]
```

### Core Python Implementation Module

Python

```
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render total page numbers 
    along with a professional running footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Footer text line
        footer_text = f"Competepulse Intelligence Brief  |  Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 36, 25, footer_text)
        
        # Top accent rule line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 40, letter[0] - 36, 40)
        
        self.restoreState()


def generate_executive_pdf(summary_data: dict, filename: str = "competepulse_brief.pdf"):
    # 1. Setup Document Template (0.5 inch margins = 36 points)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=40,
        bottomMargin=50
    )
    
    story = []
    base_styles = getSampleStyleSheet()
    
    # 2. Define Professional Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=base_styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=18
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=base_styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=8
    )

    # 3. Assemble Header Section
    story.append(Paragraph("Competepulse Weekly Intelligence Brief", title_style))
    story.append(Paragraph(f"Target Domain: <b>{summary_data.get('domain', 'N/A')}</b> &nbsp;|&nbsp; Generated automatically via Vector Diff Analysis", subtitle_style))
    story.append(Spacer(1, 8))

    # 4. Iterate and Append Dynamic Sections (Pricing, Launches, Terms)
    sections = [
        ("Pricing Shifts & Tier Modifications", summary_data.get('pricing_shifts', [])),
        ("Product Launches & Feature Updates", summary_data.get('product_launches', [])),
        ("Terms of Service & Policy Diffs", summary_data.get('terms_updates', []))
    ]

    for section_title, items in sections:
        if items:
            story.append(Paragraph(section_title, heading_style))
            for item in items:
                story.append(Paragraph(f"• {item}", body_style))
            story.append(Spacer(1, 4))

    # 5. Optional Structured Table Component (e.g., Comparative Breakdown)
    if "pricing_table" in summary_data:
        story.append(Paragraph("Comparative Tier Breakdown", heading_style))
        table_data = [["Plan", "Previous", "Current", "Delta Status"]] + summary_data['pricing_table']
        
        t = Table(table_data, colWidths=[100, 100, 100, 240])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1A202C")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # 6. Build Document using Numbered Canvas for dynamic page tracking
    doc.build(story, canvasmaker=NumberedCanvas)
```

## 5. Design & Styling Specifications

|**Design Element**|**Specification Rule**|**Purpose**|
|---|---|---|
|**Page Geometry**|Letter Size, Uniform Margins (`36pt` / 0.5 inch sides)|Optimizes whitespace for enterprise viewing or physical printing.|
|**Color Palette**|Slate/Neutral Dark (`#1A202C` text, `#2D3748` subheadings, `#EDF2F7`table headers)|Delivers a clean, modern aesthetic matching modern SaaS executive reports.|
|**Typography Scaling**|Title (`22pt`/`26pt` leading), Section (`14pt`/`18pt` leading), Body (`10pt`/`15pt` leading)|Prevents text collisions and ensures high readability across devices.|
|**Orphan Control**|`keepWithNext=True` applied to all `ParagraphStyle` headers|Automatically pins section headings to their succeeding paragraphs, preventing headings from sitting isolated at the bottom of a page.|
|**Dynamic Footers**|Two-pass custom `NumberedCanvas` rendering _"Page X of Y"_|Provides professional context for multi-page deep dive reports.|
  
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
   [[Programmatic PDF Brief Generation]]
9. 