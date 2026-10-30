"""Convert the competition draft markdown into a properly formatted Word file.

Formatting follows the usual Chinese academic/official document conventions:
A4, 2.54cm top/bottom and 3.17cm left/right margins, 小四 (12pt) 宋体 body text
with 1.5 line spacing and a two-character first-line indent, plus 黑体 headings.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
SOURCE = DOCS / '智慧城市大赛-项目说明书-初稿.md'
TARGET = DOCS / '智慧城市大赛-项目说明书-初稿.docx'

BODY_FONT = '宋体'
HEAD_FONT = '黑体'
LATIN_FONT = 'Times New Roman'
MONO_FONT = 'Consolas'


def set_fonts(run, east_asian, latin=LATIN_FONT):
    run.font.name = latin
    run._element.rPr.rFonts.set(qn('w:eastAsia'), east_asian)


def add_page_number(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement('w:fldChar')
    begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'PAGE'
    end = OxmlElement('w:fldChar')
    end.set(qn('w:fldCharType'), 'end')
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    set_fonts(run, BODY_FONT)
    run.font.size = Pt(9)


def body_paragraph(document, first_line_indent=True):
    paragraph = document.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    fmt.space_after = Pt(0)
    if first_line_indent:
        fmt.first_line_indent = Pt(24)  # two 12pt characters
    return paragraph


def add_runs(paragraph, text, size=12, east_asian=BODY_FONT, bold_all=False):
    """Split **bold** markers into separate runs."""
    for index, piece in enumerate(re.split(r'\*\*(.+?)\*\*', text)):
        if not piece:
            continue
        run = paragraph.add_run(piece)
        set_fonts(run, east_asian)
        run.font.size = Pt(size)
        run.bold = bold_all or index % 2 == 1


def add_heading(document, text, size, east_asian=HEAD_FONT, align=None,
                before=12, after=6):
    paragraph = document.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if align is not None:
        paragraph.alignment = align
    add_runs(paragraph, text, size=size, east_asian=east_asian, bold_all=(east_asian == HEAD_FONT))
    return paragraph


def add_code_block(document, lines):
    paragraph = document.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(6)
    fmt.left_indent = Cm(0.75)
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        set_fonts(run, BODY_FONT, MONO_FONT)
        run.font.size = Pt(9)
        if index != len(lines) - 1:
            run.add_break()
    return paragraph


def main():
    text = SOURCE.read_text(encoding='utf-8')
    document = Document()

    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)

    normal = document.styles['Normal']
    normal.font.size = Pt(12)
    normal.font.name = LATIN_FONT
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), BODY_FONT)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_fonts(footer.add_run('第 '), BODY_FONT)
    add_page_number(footer)
    set_fonts(footer.add_run(' 页'), BODY_FONT)
    for run in footer.runs:
        run.font.size = Pt(9)

    lines = text.splitlines()
    in_code = False
    code_lines = []
    first_heading_seen = set()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code:
                add_code_block(document, code_lines)
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if stripped == '---' or not stripped:
            continue

        if stripped.startswith('# '):
            add_heading(document, stripped[2:].strip(), 15, HEAD_FONT,
                        WD_ALIGN_PARAGRAPH.CENTER, before=0, after=6)
            continue
        if stripped.startswith('## '):
            title = stripped[3:].strip()
            if not first_heading_seen:
                first_heading_seen.add(title)
                add_heading(document, title, 22, HEAD_FONT,
                            WD_ALIGN_PARAGRAPH.CENTER, before=6, after=18)
            else:
                add_heading(document, title, 16, HEAD_FONT, before=18, after=8)
            continue
        if stripped.startswith('### '):
            add_heading(document, stripped[4:].strip(), 14, HEAD_FONT,
                        before=12, after=6)
            continue

        if stripped.startswith('**项目名称'):
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(12)
            add_runs(paragraph, stripped, size=14)
            continue

        if re.match(r'^[-*]\s+', stripped):
            paragraph = body_paragraph(document, first_line_indent=False)
            paragraph.paragraph_format.left_indent = Cm(0.75)
            paragraph.paragraph_format.first_line_indent = Cm(-0.4)
            add_runs(paragraph, '· ' + re.sub(r'^[-*]\s+', '', stripped))
            continue

        if re.match(r'^\d+\.\s+', stripped):
            paragraph = body_paragraph(document, first_line_indent=False)
            paragraph.paragraph_format.left_indent = Cm(0.75)
            paragraph.paragraph_format.first_line_indent = Cm(-0.75)
            add_runs(paragraph, stripped)
            continue

        paragraph = body_paragraph(document)
        add_runs(paragraph, stripped)

    document.save(TARGET)
    print('已生成:', TARGET)
    print('大小: %.1f KB' % (TARGET.stat().st_size / 1024))


if __name__ == '__main__':
    sys.exit(main())
