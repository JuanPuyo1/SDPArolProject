import os
import re
import sys
import time
from pathlib import Path
import pymupdf

def is_header_line(line: str) -> tuple[bool, int]:
    """Detect if a text line looks like a chapter/section heading."""
    line_clean = line.strip()
    if not line_clean:
        return False, 0
    # Match patterns like "1. CERTIFICATIONS", "CHAPTER 5", "5.2 LUBRICATION", "A. GENERAL INFORMATION"
    if re.match(r'^(CHAPTER|SEZIONE|SECTION|CAPITOLO)\s+\d+', line_clean, re.IGNORECASE):
        return True, 1
    if re.match(r'^\d+\.\d+\.\d+\s+[A-Z]', line_clean):
        return True, 3
    if re.match(r'^\d+\.\d+\s+[A-Z]', line_clean):
        return True, 2
    if re.match(r'^\d+\.\s+[A-Z]', line_clean):
        return True, 1
    if re.match(r'^[A-Z][A-Z\s]{4,60}$', line_clean) and len(line_clean.split()) <= 8:
        return True, 2
    return False, 0

def format_table_to_markdown(table) -> str:
    """Format a PyMuPDF Table object into a markdown table."""
    try:
        data = table.extract()
        if not data or len(data) == 0:
            return ""
        
        # Clean cell text
        cleaned_data = []
        for row in data:
            cleaned_row = []
            for cell in row:
                cell_str = str(cell or '').replace('\n', ' ').strip()
                cell_str = cell_str.replace('|', '\\|')
                cleaned_row.append(cell_str)
            cleaned_data.append(cleaned_row)
            
        # Determine column count
        col_count = max(len(r) for r in cleaned_data)
        if col_count == 0:
            return ""
            
        # Standardize row lengths
        for r in cleaned_data:
            while len(r) < col_count:
                r.append('')
                
        md_lines = []
        # Header row
        header = cleaned_data[0]
        md_lines.append('| ' + ' | '.join(header) + ' |')
        md_lines.append('| ' + ' | '.join(['---'] * col_count) + ' |')
        
        # Body rows
        for row in cleaned_data[1:]:
            # Ignore completely empty rows
            if any(c for c in row):
                md_lines.append('| ' + ' | '.join(row) + ' |')
                
        return '\n'.join(md_lines)
    except Exception:
        return ""

def extract_pdf_complete(pdf_path: Path) -> tuple[str, int, int]:
    """Extract complete textual content and tables from PDF into Markdown."""
    doc = pymupdf.open(str(pdf_path))
    num_pages = len(doc)
    pages_markdown = []
    total_tables_found = 0
    
    for page_idx in range(num_pages):
        page = doc[page_idx]
        page_md_blocks = []
        
        # 1. Attempt table extraction
        table_rects = []
        table_markdowns = []
        try:
            tabs = page.find_tables()
            table_list = tabs.tables if hasattr(tabs, 'tables') else list(tabs)
            for t in table_list:
                if hasattr(t, 'bbox') and t.bbox:
                    t_rect = pymupdf.Rect(t.bbox)
                    # Filter out degenerate zero-area bounding boxes
                    if t_rect.width > 10 and t_rect.height > 10:
                        t_md = format_table_to_markdown(t)
                        if t_md:
                            table_rects.append(t_rect)
                            table_markdowns.append(t_md)
                            total_tables_found += 1
        except Exception:
            table_rects = []
            table_markdowns = []

        # 2. Extract text blocks
        blocks = page.get_text('blocks')
        
        # Process blocks in reading order (top-to-bottom, left-to-right)
        blocks_sorted = sorted(blocks, key=lambda b: (b[1], b[0]))
        
        non_table_text_blocks = []
        for b in blocks_sorted:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if b[6] == 0:  # Text block
                block_text = b[4].strip()
                if not block_text:
                    continue
                    
                block_rect = pymupdf.Rect(b[:4])
                
                # Check if block is inside an extracted table to avoid duplication
                is_in_table = False
                for tr in table_rects:
                    # If block significantly overlaps with a table rect
                    intersect = block_rect.intersect(tr)
                    if intersect.width > 0 and intersect.height > 0:
                        overlap_area = intersect.width * intersect.height
                        block_area = max(1, block_rect.width * block_rect.height)
                        if (overlap_area / block_area) > 0.4:
                            is_in_table = True
                            break
                            
                if not is_in_table:
                    # Format headings if detected
                    is_h, level = is_header_line(block_text)
                    if is_h and '\n' not in block_text:
                        prefix = '#' * level + ' '
                        block_text = prefix + block_text
                    non_table_text_blocks.append(block_text)
                    
        # Combine non-table text blocks and formatted markdown tables
        page_content = []
        if non_table_text_blocks:
            page_content.append('\n\n'.join(non_table_text_blocks))
        if table_markdowns:
            page_content.append('\n\n### Extracted Tables\n\n' + '\n\n'.join(table_markdowns))
            
        full_page_str = f"<!-- Page {page_idx + 1} -->\n\n" + '\n\n'.join(page_content)
        pages_markdown.append(full_page_str)
        
    doc.close()
    full_markdown = '\n\n---\n\n'.join(pages_markdown)
    return full_markdown, num_pages, total_tables_found

def main():
    script_dir = Path(__file__).resolve().parent
    manuals_dir = script_dir / "Manuals_pdf"
    output_dir = script_dir / "Manuals_md"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = sorted([p for p in manuals_dir.glob("*.pdf")])
    
    print(f"==================================================")
    print(f"COMPLETE PDF TEXT & TABLE EXTRACTION PIPELINE")
    print(f"Source Directory: {manuals_dir}")
    print(f"Target Directory: {output_dir}")
    print(f"Processing {len(pdf_files)} Manual PDFs...")
    print(f"==================================================\n")
    
    summary = []
    total_start = time.time()
    
    for pdf_path in pdf_files:
        print(f"--> Extracting: {pdf_path.name}")
        start = time.time()
        try:
            full_md, num_pages, tables_found = extract_pdf_complete(pdf_path)
            
            out_file = output_dir / f"{pdf_path.stem}.md"
            out_file.write_text(full_md, encoding="utf-8")
            
            elapsed = time.time() - start
            size_kb = out_file.stat().st_size / 1024
            word_count = len(full_md.split())
            line_count = len(full_md.splitlines())
            
            print(f"    ✓ Extracted to : Data/Manuals_md/{out_file.name}")
            print(f"    ✓ Pages        : {num_pages} pages")
            print(f"    ✓ Tables Found : {tables_found} tables formatted")
            print(f"    ✓ Text Stats   : {line_count:,} lines | {word_count:,} words | {size_kb:.1f} KB")
            print(f"    ✓ Time Elapsed : {elapsed:.2f}s ({elapsed / max(1, num_pages):.2f}s/page)\n")
            
            summary.append((pdf_path.name, out_file.name, num_pages, tables_found, word_count, line_count, size_kb, elapsed))
        except Exception as e:
            print(f"    ✗ ERROR processing {pdf_path.name}: {e}\n")
            import traceback
            traceback.print_exc()

    total_elapsed = time.time() - total_start
    print("="*65)
    print("             FULL EXTRACTION SUMMARY REPORT")
    print("="*65)
    print(f"Successfully processed : {len(summary)} / {len(pdf_files)} manuals")
    print(f"Total time elapsed     : {total_elapsed:.2f} seconds")
    print("-"*65)
    for orig, out_name, pages, tables, words, lines, size_kb, elapsed in summary:
        print(f" • {orig}")
        print(f"   ├─ Extracted File : Data/Manuals_md/{out_name}")
        print(f"   └─ Metrics        : {pages} pages | {tables} tables | {words:,} words | {size_kb:.1f} KB ({elapsed:.1f}s)")
    print("="*65)

if __name__ == "__main__":
    main()
