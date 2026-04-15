"""
One-time preprocessing script: converts a PDF presentation into PNGs,
extracts text, generates AI narrations via Claude, and outputs
slides_data.json + frontend assets.

Usage:
    cd backend && python preprocess.py
"""

import json
import os
import shutil
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (all relative to this script's location, i.e. backend/)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PDF_PATH = SCRIPT_DIR / ".." / "data" / "slides.pdf"
SLIDES_IMG_DIR = SCRIPT_DIR / ".." / "data" / "slides"
SLIDES_JSON_PATH = SCRIPT_DIR / ".." / "data" / "slides_data.json"
FRONTEND_SLIDES_DIR = SCRIPT_DIR / ".." / "frontend" / "public" / "slides"
FRONTEND_SLIDES_JS = SCRIPT_DIR / ".." / "frontend" / "src" / "slides.js"

PNG_WIDTH = 1920  # target width in pixels
CLAUDE_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_dirs():
    """Create output directories if they don't exist."""
    for d in [SLIDES_IMG_DIR, FRONTEND_SLIDES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    # Also ensure parent dir for slides.js exists
    FRONTEND_SLIDES_JS.parent.mkdir(parents=True, exist_ok=True)


def convert_pdf_to_pngs(pdf_path: Path, output_dir: Path) -> list[Path]:
    """Convert each PDF page to a high-quality PNG using pdf2image."""
    from pdf2image import convert_from_path

    print(f"Converting PDF to PNGs (width={PNG_WIDTH}px)...")
    images = convert_from_path(str(pdf_path), size=(PNG_WIDTH, None))

    paths: list[Path] = []
    for i, img in enumerate(images):
        out = output_dir / f"slide_{i}.png"
        img.save(str(out), "PNG")
        paths.append(out)
        print(f"  Saved {out.name}")

    print(f"Converted {len(images)} pages.\n")
    return paths


def extract_text_per_page(pdf_path: Path) -> list[str]:
    """Extract text from each page using pdfplumber."""
    import pdfplumber

    print("Extracting text from PDF...")
    texts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            texts.append(text.strip())
            preview = text[:80].replace("\n", " ") if text else "(empty)"
            print(f"  Page {i}: {preview}...")

    print(f"Extracted text from {len(texts)} pages.\n")
    return texts


def generate_narration(client: Anthropic, slide_index: int, extracted_text: str, image_path: Path) -> dict:
    """
    Call Claude with the slide IMAGE (vision) + extracted text to generate
    a title, narration script, and keywords. Vision lets Claude understand
    diagrams, charts, and visual elements that text extraction misses.
    """
    import base64

    # Read the slide PNG and encode as base64
    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = f"""You are helping create a narrated presentation. This is slide {slide_index + 1}.

I'm showing you the actual slide image. Also, here is the raw extracted text (may be incomplete or miss visual elements):
\"\"\"
{extracted_text}
\"\"\"

Look at BOTH the image and the text. The image may contain diagrams, charts, illustrations, or visual layouts that the text doesn't capture.

Based on everything you see, generate:
1. A clean, presentation-ready title (short, descriptive).
2. A narration script: 5-6 natural spoken sentences that a presenter would say to cover ALL the content on this slide — including any diagrams, images, or visual elements you can see. The narration should sound conversational and engaging, as if a real person is presenting live to an audience.
3. A list of 5-8 routing keywords that capture the main topics of this slide (used for matching user questions to the right slide).

Return ONLY valid JSON in this exact format, with no markdown fencing or extra text:
{{"title": "...", "narration": "...", "keywords": ["...", "..."]}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }],
    )

    # Parse the response text as JSON, stripping markdown fencing if present
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def build_slide_data(
    client: Anthropic,
    texts: list[str],
    png_names: list[str],
    png_dir: Path,
) -> list[dict]:
    """For each slide, call Claude with the image + text for narration."""
    slides_data: list[dict] = []

    for i, text in enumerate(texts):
        image_path = png_dir / png_names[i]
        print(f"Generating narration for slide {i} ({png_names[i]}) using vision...")

        try:
            ai = generate_narration(client, i, text, image_path)
            title = ai.get("title", f"Slide {i + 1}")
            narration = ai.get("narration", text)
            keywords = ai.get("keywords", [])
        except Exception as e:
            print(f"  WARNING: Claude failed for slide {i}: {e}")
            print(f"  Using extracted text as fallback narration.")
            title = f"Slide {i + 1}"
            narration = text if text else f"This is slide {i + 1}."
            keywords = []

        entry = {
            "index": i,
            "title": title,
            "extracted_text": text,
            "narration": narration,
            "keywords": keywords,
            "image": png_names[i],
        }
        slides_data.append(entry)
        print(f"  Title: {title}")
        print(f"  Narration: {narration[:100]}...")
        print()

    return slides_data


def save_json(data: list[dict], path: Path):
    """Write slides_data.json."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved slides data to {path}\n")


def copy_pngs_to_frontend(src_dir: Path, dst_dir: Path):
    """Copy all PNGs to frontend/public/slides/ for Vite static serving."""
    print("Copying PNGs to frontend/public/slides/...")
    dst_dir.mkdir(parents=True, exist_ok=True)
    for png in sorted(src_dir.glob("slide_*.png")):
        dest = dst_dir / png.name
        shutil.copy2(str(png), str(dest))
        print(f"  {png.name} -> {dest}")
    print()


def generate_frontend_slides_js(data: list[dict], path: Path):
    """Generate frontend/src/slides.js from the processed data."""
    entries = []
    for slide in data:
        entry = (
            f'  {{ index: {slide["index"]}, '
            f'title: {json.dumps(slide["title"])}, '
            f'image: "/slides/{slide["image"]}" }}'
        )
        entries.append(entry)

    js = "export const SLIDES = [\n" + ",\n".join(entries) + ",\n];\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"Generated {path}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    # Load environment variables from backend/.env
    env_path = SCRIPT_DIR / ".env"
    load_dotenv(env_path)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment or backend/.env")
        sys.exit(1)

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    print(f"PDF: {PDF_PATH}")
    print(f"Model: {CLAUDE_MODEL}")
    print()

    # Step 0: Create directories
    ensure_dirs()

    # Step 1: Convert PDF to PNGs
    png_paths = convert_pdf_to_pngs(PDF_PATH, SLIDES_IMG_DIR)
    png_names = [p.name for p in png_paths]

    # Step 2: Extract text from each page
    texts = extract_text_per_page(PDF_PATH)

    # Sanity check: page count should match
    if len(png_paths) != len(texts):
        print(
            f"WARNING: PNG count ({len(png_paths)}) != text page count ({len(texts)}). "
            f"Using min of both."
        )
        count = min(len(png_paths), len(texts))
        png_names = png_names[:count]
        texts = texts[:count]

    # Step 3: Generate narrations via Claude
    client = Anthropic(api_key=api_key)
    slides_data = build_slide_data(client, texts, png_names, SLIDES_IMG_DIR)

    # Step 4: Save slides_data.json
    save_json(slides_data, SLIDES_JSON_PATH)

    # Step 5: Copy PNGs to frontend/public/slides/
    copy_pngs_to_frontend(SLIDES_IMG_DIR, FRONTEND_SLIDES_DIR)

    # Step 6: Generate frontend/src/slides.js
    generate_frontend_slides_js(slides_data, FRONTEND_SLIDES_JS)

    print("=" * 60)
    print("Preprocessing complete!")
    print(f"  Slides processed: {len(slides_data)}")
    print(f"  JSON: {SLIDES_JSON_PATH}")
    print(f"  PNGs: {SLIDES_IMG_DIR}")
    print(f"  Frontend PNGs: {FRONTEND_SLIDES_DIR}")
    print(f"  Frontend JS: {FRONTEND_SLIDES_JS}")
    print("=" * 60)


if __name__ == "__main__":
    main()
