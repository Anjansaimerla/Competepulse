Here is a detailed, step-by-step breakdown of how the **Programmatic PDF Brief Generation** layer works in **Competepulse**.

  

### Overview: What is Programmatic PDF Generation?

Instead of a human sitting down in Microsoft Word or Google Docs to format a weekly report, this step uses code to automatically take raw text and insights from an LLM and turn them into a clean, publication-ready PDF document.

  

In _Competepulse_, this is handled by a Python library called **ReportLab**, which acts like a layout engine that builds documents programmatically from top to bottom.

  

### The 4-Step PDF Generation Pipeline

#### 1. Page Setup & Document Canvas Initialization

Before adding any content, the script sets up the boundaries of the digital canvas (the "page template").

  

- **Page Size:** Standard Letter size (`8.5 x 11 inches`).
    
      
    
- **Margins:** Strict margins (e.g., `36` points or 0.5 inches) are applied to ensure text never bleeds off the page and looks professional.
    
      
    
- **The "Story" Array:** ReportLab uses a concept called a story. Think of it like an empty conveyor belt. You append elements (titles, paragraphs, spacers, tables) to this array sequentially, and ReportLab automatically calculates how they flow across page breaks.
    
      
    

Python

```
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate

# Initialize the document canvas
doc = SimpleDocTemplate(
    "executive_brief.pdf", 
    pagesize=letter, 
    rightMargin=36, 
    leftMargin=36, 
    topMargin=36, 
    bottomMargin=36
)
story = [] # The conveyor belt for our content
```

#### 2. Defining Professional Typography & Styles

Raw unstyled text looks like a broken plain-text file. To make it look like an elite executive brief, custom styles are defined using ReportLab’s `ParagraphStyle`.

  

- **Hierarchy:** Distinct styles are created for Document Titles, Section Headings (`h2`), Body Text, and Bullet Points.
    
      
    
- **Font & Spacing:** Consistent fonts (like Helvetica or Times-Roman) are paired with precise line heights and spacing after elements (`spaceAfter=12`) so text blocks don't cramp each other.
    
      
    

Python

```
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

styles = getSampleStyleSheet()

# Custom Title Style
title_style = ParagraphStyle(
    'ExecutiveTitle',
    parent=styles['Heading1'],
    fontSize=20,
    leading=24,
    textColor=colors.HexColor("#1A202C"), # Dark slate gray
    spaceAfter=12
)

# Custom Body Style
body_style = ParagraphStyle(
    'ExecutiveBody',
    parent=styles['Normal'],
    fontSize=10,
    leading=14,
    textColor=colors.HexColor("#4A5568"),
    spaceAfter=8
)
```

#### 3. Data Assembly (Injecting LLM Insights)

Once the LLM returns its structured analysis (Pricing Shifts, Product Launches, Terms Updates), the script loops through the data, wraps each piece in its respective style, and pushes it onto the story conveyor belt.

  

- **Spacers:** Explicit vertical gaps (`Spacer(1, 10)`) are added between sections to maintain breathing room.
    
      
    
- **Tables (Optional for Pricing):** For pricing tier comparisons, a ReportLab `Table` object is constructed, allowing the script to draw gridlines, align text cleanly, and alternate row background colors for legibility.
    
      
    

Python

```
from reportlab.platypus import Paragraph, Spacer

# 1. Add Title
story.append(Paragraph("Competepulse Weekly Intelligence Brief", title_style))
story.append(Spacer(1, 15))

# 2. Add Section Heading
story.append(Paragraph("<b>1. Pricing & Packaging Shifts</b>", styles['Heading2']))
story.append(Spacer(1, 6))

# 3. Add Body Text synthesized from LLM analysis
pricing_insights = "Competitor X has quietly increased their Pro tier from $39/mo to $49/mo, while lowering the included user seat limit from 5 down to 3."
story.append(Paragraph(pricing_insights, body_style))
story.append(Spacer(1, 12))
```

#### 4. Compilation & Output

Once all elements are pushed into the story list, a single command tells ReportLab to compile the layout, calculate page breaks automatically, and write the final file to disk or cloud storage.

  

Python

```
# Build the PDF file
doc.build(story)
```

### Why Programmatic PDF Generation Matters for Competepulse

1. **Zero Manual Friction:** It completely automates the final mile of the workflow. The user doesn't have to copy-paste LLM text into Notion or Word; a polished PDF is ready the second the script finishes.
    
      
    
2. **Executive Ready:** By enforcing strict layout rules, margins, and color palettes, every generated brief looks uniform, branded, and professional enough to hand directly to stakeholders or management.
    
      
    
3. **Cloud Compatible:** Because ReportLab runs entirely via code inside Python, it can execute seamlessly inside a Docker container on GitHub Actions or AWS Lambda without needing a graphical desktop interface.
   
     
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
   [[pdfrules]]
10. [[Serverless & Scheduled Automation]]
11. 