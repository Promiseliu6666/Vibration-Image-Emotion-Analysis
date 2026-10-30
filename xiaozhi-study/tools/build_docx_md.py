"""把任意 Markdown 项目文档排版成 Word，复用 build_docx.py 的字体与版式设定。

    python tools/build_docx_md.py docs/附件2项目文档-智慧生活与大健康版.md [输出.docx]

相比 build_docx.py 增加了两件事：Markdown 表格 → Word 表格、引用行（>）→ 灰色小字。
版式沿用同一套约定：A4、页边距 2.54/3.17cm、正文宋体小四、1.5 倍行距、首行缩进 2 字符、
标题黑体、页脚页码。
"""
import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_docx import (  # noqa: E402  复用同一套版式设定
    BODY_FONT, HEAD_FONT, LATIN_FONT,
    add_code_block, add_heading, add_page_number, add_runs, body_paragraph, set_fonts,
)


def add_table(document, rows, size=10.5):
    """rows: list[list[str]]，第一行当表头。"""
    table = document.add_table(rows=0, cols=len(rows[0]))
    table.style = 'Table Grid'
    for row_index, cells in enumerate(rows):
        row = table.add_row()
        for cell, text in zip(row.cells, cells):
            paragraph = cell.paragraphs[0]
            fmt = paragraph.paragraph_format
            fmt.space_after = Pt(0)
            fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
            add_runs(paragraph, text, size=size, bold_all=(row_index == 0))
    spacing = document.add_paragraph()
    spacing.paragraph_format.space_after = Pt(6)
    return table


def is_separator(cells):
    return all(re.fullmatch(r':?-{2,}:?', c) for c in cells if c)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Markdown 源文件')
    parser.add_argument('target', nargs='?', type=Path, help='输出 docx（默认同名）')
    args = parser.parse_args(argv)

    source = args.source.resolve()
    target = (args.target or source.with_suffix('.docx')).resolve()
    lines = source.read_text(encoding='utf-8').splitlines()

    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.54)
    section.left_margin = section.right_margin = Cm(3.17)

    normal = document.styles['Normal']
    normal.font.size = Pt(12)
    normal.font.name = LATIN_FONT
    from docx.oxml.ns import qn
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), BODY_FONT)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_fonts(footer.add_run('第 '), BODY_FONT)
    add_page_number(footer)
    set_fonts(footer.add_run(' 页'), BODY_FONT)
    for run in footer.runs:
        run.font.size = Pt(9)

    in_code, code_lines = False, []
    first_heading_seen = False
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()

        if stripped.startswith('```'):
            if in_code:
                add_code_block(document, code_lines)
                code_lines, in_code = [], False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(lines[index].rstrip())
            index += 1
            continue
        if stripped == '---' or not stripped:
            index += 1
            continue

        if stripped.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                cells = [c.strip().replace('\\|', '|') for c in lines[index].strip().strip('|').split('|')]
                if not is_separator(cells):
                    rows.append(cells)
                index += 1
            if rows:
                add_table(document, rows)
            continue

        if stripped.startswith('# '):
            add_heading(document, stripped[2:].strip(), 15, HEAD_FONT,
                        WD_ALIGN_PARAGRAPH.CENTER, before=0, after=6)
            index += 1
            continue
        if stripped.startswith('## '):
            title = stripped[3:].strip()
            if not first_heading_seen:
                first_heading_seen = True
                add_heading(document, title, 20, HEAD_FONT,
                            WD_ALIGN_PARAGRAPH.CENTER, before=6, after=14)
            else:
                add_heading(document, title, 16, HEAD_FONT, before=18, after=8)
            index += 1
            continue
        if stripped.startswith('### '):
            add_heading(document, stripped[4:].strip(), 14, HEAD_FONT, before=12, after=6)
            index += 1
            continue
        if stripped.startswith('#### '):
            add_heading(document, stripped[5:].strip(), 12.5, HEAD_FONT, before=10, after=4)
            index += 1
            continue

        if stripped.startswith('**项目名称'):
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(12)
            add_runs(paragraph, stripped, size=14)
            index += 1
            continue

        if stripped.startswith('>'):
            paragraph = body_paragraph(document, first_line_indent=False)
            paragraph.paragraph_format.left_indent = Cm(0.5)
            paragraph.paragraph_format.space_after = Pt(6)
            run = paragraph.add_run(stripped.lstrip('> ').strip())
            set_fonts(run, BODY_FONT)
            run.font.size = Pt(10.5)
            run.font.color.rgb = __import__('docx').shared.RGBColor(0x66, 0x66, 0x66)
            index += 1
            continue

        if re.match(r'^[-*]\s+', stripped):
            paragraph = body_paragraph(document, first_line_indent=False)
            paragraph.paragraph_format.left_indent = Cm(0.75)
            paragraph.paragraph_format.first_line_indent = Cm(-0.4)
            add_runs(paragraph, '· ' + re.sub(r'^[-*]\s+', '', stripped))
            index += 1
            continue
        if re.match(r'^\d+\.\s+', stripped):
            paragraph = body_paragraph(document, first_line_indent=False)
            paragraph.paragraph_format.left_indent = Cm(0.75)
            paragraph.paragraph_format.first_line_indent = Cm(-0.75)
            add_runs(paragraph, stripped)
            index += 1
            continue

        paragraph = body_paragraph(document)
        add_runs(paragraph, stripped)
        index += 1

    document.save(target)
    print('已生成:', target)
    print('大小: %.1f KB' % (target.stat().st_size / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
