# Reader3 Overview

## reader3.py
- Parses an EPUB file into a structured `Book` object.
- Extracts metadata (title, authors, language, identifiers, subjects).
- Builds a table of contents tree, with a spine fallback if the EPUB lacks a TOC.
- Extracts and saves images to an `images/` folder, rewriting HTML image paths.
- Cleans HTML content (removes scripts, styles, inputs, iframes, etc.).
- Produces plain-text content for search/LLM usage.
- Serializes the processed book to `book.pkl` inside a `<book>_data` folder.

## server.py
- FastAPI app that serves a library and reader UI for processed books.
- Loads `book.pkl` from `*_data` folders, caching results in memory.
- `/` lists all available processed books.
- `/read/{book_id}` redirects to the first chapter.
- `/read/{book_id}/{chapter_index}` renders the reader UI with prev/next navigation.
- `/read/{book_id}/images/{image_name}` serves extracted images safely.
- CLI entrypoint runs the server with configurable host, port, and books directory.

## Reader Sidebar Behavior
- The sidebar renders the EPUB TOC tree (`book.toc`), including nested sections and subsections.
- Clicking a TOC item filters the list to show only that item's sub sections.
- Chapter and subsection clicks both map to the same spine file (linear chapter file).
- The JS strips anchors and routes to `/read/{book_id}/{spine_index}`, so the full chapter loads.

