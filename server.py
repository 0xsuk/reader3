import os
import pickle
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bs4 import BeautifulSoup
from bs4.element import PageElement

from reader3 import Book, BookMetadata, ChapterContent, TOCEntry

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Where are the book folders located?
BOOKS_DIR = "."

@lru_cache(maxsize=10)
def load_book_cached(folder_name: str) -> Optional[Book]:
    """
    Loads the book from the pickle file.
    Cached so we don't re-read the disk on every click.
    """
    file_path = os.path.join(BOOKS_DIR, folder_name, "book.pkl")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            book = pickle.load(f)
        return book
    except Exception as e:
        print(f"Error loading book {folder_name}: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def library_view(request: Request):
    """Lists all available processed books."""
    books = []

    # Scan directory for folders ending in '_data' that have a book.pkl
    if os.path.exists(BOOKS_DIR):
        for item in os.listdir(BOOKS_DIR):
            item_path = os.path.join(BOOKS_DIR, item)
            if item.endswith("_data") and os.path.isdir(item_path):
                # Try to load it to get the title
                book = load_book_cached(item)
                if book:
                    books.append({
                        "id": item,
                        "title": book.metadata.title,
                        "author": ", ".join(book.metadata.authors),
                        "chapters": len(book.spine)
                    })

    return templates.TemplateResponse("library.html", {"request": request, "books": books})

@app.get("/read/{book_id}", response_class=HTMLResponse)
async def redirect_to_first_chapter(request: Request, book_id: str):
    """Helper to just go to chapter 0."""
    return await read_chapter(request=request, book_id=book_id, chapter_index=0)

def build_subsection_content(html: str, anchor: Optional[str]) -> Optional[str]:
    if not anchor:
        return None

    soup = BeautifulSoup(html, "html.parser")
    target = soup.find(id=anchor)
    if not target:
        target = soup.find(attrs={"name": anchor})
    if not target:
        target = soup.find("a", href=f"#{anchor}")
    if not target:
        return None

    heading_levels = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def get_heading_level(node: object) -> Optional[int]:
        node_name = getattr(node, "name", None)
        if isinstance(node_name, str) and node_name in heading_levels:
            return int(node_name[1])
        return None

    start = target
    start_level = get_heading_level(start)
    if start_level is None:
        heading_parent = target.find_parent(heading_levels)
        if heading_parent is not None:
            start = heading_parent
            start_level = get_heading_level(start)

    section_nodes: list[PageElement] = [start]
    for sibling in list(start.next_siblings):
        sibling_name = getattr(sibling, "name", None)
        if isinstance(sibling_name, str) and sibling_name in heading_levels:
            sibling_level = int(sibling_name[1])
            if start_level is None or sibling_level <= start_level:
                break
        section_nodes.append(sibling)

    return "".join(str(node) for node in section_nodes)


@app.get("/read/{book_id}/{chapter_index}", response_class=HTMLResponse)
async def read_chapter(request: Request, book_id: str, chapter_index: int):
    """The main reader interface."""
    book = load_book_cached(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if chapter_index < 0 or chapter_index >= len(book.spine):
        raise HTTPException(status_code=404, detail="Chapter not found")

    current_chapter = book.spine[chapter_index]
    anchor = request.query_params.get("anchor")
    subsection_content = build_subsection_content(current_chapter.content, anchor)

    if subsection_content is not None:
        current_chapter = ChapterContent(
            id=current_chapter.id,
            href=current_chapter.href,
            title=current_chapter.title,
            content=subsection_content,
            text=current_chapter.text,
            order=current_chapter.order,
        )

    # Calculate Prev/Next links
    prev_idx = chapter_index - 1 if chapter_index > 0 else None
    next_idx = chapter_index + 1 if chapter_index < len(book.spine) - 1 else None

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "book": book,
        "current_chapter": current_chapter,
        "chapter_index": chapter_index,
        "book_id": book_id,
        "prev_idx": prev_idx,
        "next_idx": next_idx,
        "anchor": anchor,
        "is_subsection": subsection_content is not None,
    })

@app.get("/read/{book_id}/images/{image_name}")
async def serve_image(book_id: str, image_name: str):
    """
    Serves images specifically for a book.
    The HTML contains <img src="images/pic.jpg">.
    The browser resolves this to /read/{book_id}/images/pic.jpg.
    """
    # Security check: ensure book_id is clean
    safe_book_id = os.path.basename(book_id)
    safe_image_name = os.path.basename(image_name)

    img_path = os.path.join(BOOKS_DIR, safe_book_id, "images", safe_image_name)

    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(img_path)

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the reader server")
    parser.add_argument("--books-dir", default=BOOKS_DIR, help="Directory containing *_data book folders")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    BOOKS_DIR = args.books_dir
    print(f"Starting server at http://{args.host}:{args.port} (books dir: {BOOKS_DIR})")
    uvicorn.run(app, host=args.host, port=args.port)
