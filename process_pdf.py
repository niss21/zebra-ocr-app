import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import pytesseract


def process_pdf(INPUT_PDF, OUTPUT_DIR):
    RECEIPTS_PER_PAGE = 3
    LEFT_RATIO = 0.5

    # OCR
    OCR_DPI = 300

    # Zebra ZD230 (4 x 3 inch)
    PRINTER_DPI = 203
    LABEL_W = int(4 * PRINTER_DPI)   # 812 px
    LABEL_H = int(3 * PRINTER_DPI)   # 609 px

    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ================= HELPERS =================
    def wrap_text(text, font, max_width, draw):
        words = text.split()
        lines = []
        current = ""

        for word in words:
            test = current + (" " if current else "") + word
            if draw.textlength(test, font=font) <= max_width:
                current = test
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)
        return lines

    # ================= STEP 1: PDF → IMAGES =================
    subprocess.run([
        "pdftoppm", "-r", str(OCR_DPI),
        INPUT_PDF, "page", "-png"
    ], check=True)

    # ================= STEP 2: PROCESS =================
    for page_img in sorted(f for f in os.listdir(".") if f.startswith("page-") and f.endswith(".png")):
        page = Image.open(page_img)
        pw, ph = page.size
        receipt_h = ph // RECEIPTS_PER_PAGE

        for i in range(RECEIPTS_PER_PAGE):
            receipt = page.crop((0, i * receipt_h, pw, (i + 1) * receipt_h))
            receipt = receipt.crop((0, 0, int(receipt.width * LEFT_RATIO), receipt.height))

            receipt_ocr = ImageOps.autocontrast(receipt.convert("L"), cutoff=1)

            text = pytesseract.image_to_string(
                receipt_ocr,
                lang="eng",
                config="--psm 6"
            )

            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not lines:
                continue

            # ================= STEP 3: RE-LAYOUT =================
            canvas = Image.new("L", (LABEL_W, LABEL_H), 255)
            draw = ImageDraw.Draw(canvas)

            pathao_font = ImageFont.truetype(FONT_BOLD, 42)
            header_font = ImageFont.truetype(FONT_REGULAR, 30)
            body_font = ImageFont.truetype(FONT_REGULAR, 24)

            margin_x = 30
            max_width = LABEL_W - margin_x * 2
            y = 20

            # -------- PATHAO TITLE (BOLD) --------
            brand = "PATHAO"
            bw = draw.textlength(brand, font=pathao_font)
            draw.text(((LABEL_W - bw) // 2, y), brand, font=pathao_font, fill=0)
            y += 60

            # -------- HEADER (REGULAR, CENTERED) --------
            header = lines[0].upper()
            hw = draw.textlength(header, font=header_font)
            draw.text(((LABEL_W - hw) // 2, y), header, font=header_font, fill=0)
            y += 45

            # -------- BODY (ALL REGULAR) --------
            for line in lines[1:]:
                wrapped = wrap_text(line, body_font, max_width, draw)
                for wline in wrapped:
                    if y > LABEL_H - 35:
                        break
                    draw.text((margin_x, y), wline, font=body_font, fill=0)
                    y += 30

            # ================= STEP 4: THERMAL OPTIMIZATION =================
            canvas = ImageOps.autocontrast(canvas)
            canvas = canvas.filter(
                ImageFilter.UnsharpMask(radius=1.2, percent=220, threshold=2)
            )
            canvas = canvas.point(lambda x: 0 if x < 180 else 255, "1")

            out = f"{OUTPUT_DIR}/{page_img.replace('.png','')}_receipt_{i+1}_4x3.png"
            canvas.save(out)
            print("Generated:", out)

        os.remove(page_img)

    print("\n✅ DONE — PATHAO branded Zebra-ready labels created")
