import json
import zipfile
import csv
import shutil
import html
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


def fix_encoding(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


@dataclass
class FacebookPost:
    timestamp: int
    post_text: str
    title: str
    photo_paths: list[str] = field(default_factory=list)
    photo_filenames: list[str] = field(default_factory=list)
    date_string: str = ""
    tags: list[str] = field(default_factory=list)
    external_url: str = ""

    def __post_init__(self):
        if self.timestamp:
            self.date_string = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")


def extract_posts_from_json(data: list[dict]) -> list[FacebookPost]:
    posts = []
    seen_timestamps = set()
    
    for item in data:
        timestamp = item.get("timestamp", 0)
        
        if timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)
        
        post_text = ""
        for d in item.get("data", []):
            if d.get("post"):
                post_text = fix_encoding(d["post"])
                break
        
        title = fix_encoding(item.get("title", ""))
        
        tags = [fix_encoding(t.get("name", "")) for t in item.get("tags", [])]
        
        photo_paths = []
        external_url = ""
        
        for attachment in item.get("attachments", []):
            for att_data in attachment.get("data", []):
                if att_data.get("media"):
                    media = att_data["media"]
                    uri = media.get("uri", "")
                    if uri and "sticker" not in uri.lower():
                        photo_paths.append(uri)
                
                if att_data.get("external_context"):
                    external_url = att_data["external_context"].get("url", "")
        
        if post_text or photo_paths:
            post = FacebookPost(
                timestamp=timestamp,
                post_text=post_text,
                title=title,
                photo_paths=photo_paths,
                photo_filenames=[Path(p).name for p in photo_paths],
                tags=tags,
                external_url=external_url
            )
            posts.append(post)
    
    return posts


def extract_all_zips(zip_dir: Path, extract_dir: Path) -> list[Path]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    json_files = []
    
    for zip_path in sorted(zip_dir.glob("*.zip")):
        print(f"Extracting: {zip_path.name}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.json') and 'posts' in name and 'your_posts' in name:
                    zf.extract(name, extract_dir)
                    json_files.append(extract_dir / name)
                elif '/posts/media/' in name:
                    zf.extract(name, extract_dir)
    
    return json_files


def load_and_merge_posts(json_files: list[Path]) -> list[FacebookPost]:
    all_posts = []
    seen_timestamps = set()
    
    for json_file in json_files:
        print(f"Processing: {json_file}")
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                posts = extract_posts_from_json(data)
                for post in posts:
                    if post.timestamp not in seen_timestamps:
                        seen_timestamps.add(post.timestamp)
                        all_posts.append(post)
            except json.JSONDecodeError as e:
                print(f"Error reading {json_file}: {e}")
    
    all_posts.sort(key=lambda p: p.timestamp, reverse=True)
    return all_posts


def posts_to_csv(posts: list[FacebookPost], output_path: Path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'date', 'post_text', 'title', 'photo_paths', 'photo_filenames', 'tags', 'external_url'])
        
        for post in posts:
            writer.writerow([
                post.timestamp,
                post.date_string,
                post.post_text,
                post.title,
                '|'.join(post.photo_paths),
                '|'.join(post.photo_filenames),
                '|'.join(post.tags),
                post.external_url
            ])
    
    print(f"CSV saved to: {output_path}")


def generate_html(posts: list[FacebookPost], extract_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    photos_output_dir = output_dir / "photos"
    photos_output_dir.mkdir(parents=True, exist_ok=True)
    
    def copy_photo(photo_path: str) -> str:
        src = extract_dir / photo_path
        if src.exists():
            dest = photos_output_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
            return f"photos/{src.name}"
        return ""
    
    html_items = []
    
    for i, post in enumerate(posts):
        photo_html = ""
        if post.photo_paths:
            photo_copies = []
            for p in post.photo_paths:
                copied_path = copy_photo(p)
                if copied_path:
                    photo_copies.append(f'<img src="{html.escape(copied_path)}" alt="Photo" class="post-photo">')
            if photo_copies:
                photo_html = f'<div class="photos">{"".join(photo_copies)}</div>'
        
        text_html = f'<p class="post-text">{html.escape(post.post_text)}</p>' if post.post_text else ""
        title_html = f'<p class="title">{html.escape(post.title)}</p>' if post.title else ""
        date_html = f'<span class="date">{html.escape(post.date_string)}</span>' if post.date_string else ""
        
        tags_html = ""
        if post.tags:
            tags_html = f'<div class="tags">Označení: {html.escape(", ".join(post.tags))}</div>'
        
        external_html = ""
        if post.external_url:
            external_html = f'<a href="{html.escape(post.external_url)}" target="_blank" rel="noopener" class="external-link">Externý odkaz</a>'
        
        html_items.append(f'''
        <div class="post">
            <div class="post-header">
                {date_html}
            </div>
            {title_html}
            {text_html}
            {photo_html}
            {tags_html}
            {external_html}
        </div>
        ''')
    
    html_content = f'''<!DOCTYPE html>
<html lang="sk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archív Facebook príspevkov</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f0f2f5;
            padding: 20px;
            color: #1c1e21;
        }}
        .container {{
            max-width: 680px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 20px;
            color: #1877f2;
        }}
        .stats {{
            text-align: center;
            margin-bottom: 20px;
            color: #65676b;
        }}
        .post {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            margin-bottom: 15px;
            padding: 15px;
        }}
        .post-header {{
            margin-bottom: 10px;
        }}
        .date {{
            color: #65676b;
            font-size: 0.9em;
        }}
        .title {{
            color: #65676b;
            font-size: 0.85em;
            margin-bottom: 8px;
        }}
        .post-text {{
            font-size: 15px;
            line-height: 1.5;
            margin-bottom: 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .photos {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .post-photo {{
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            object-fit: contain;
            cursor: pointer;
        }}
        .tags {{
            margin-top: 10px;
            color: #1877f2;
            font-size: 0.9em;
        }}
        .external-link {{
            display: inline-block;
            margin-top: 10px;
            color: #1877f2;
            text-decoration: none;
        }}
        .external-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Archív Facebook príspevkov</h1>
        <p class="stats">Celkom príspevkov: {len(posts)}</p>
        {"".join(html_items)}
    </div>
</body>
</html>
'''
    
    output_path = output_dir / "index.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML saved to: {output_path}")
    print(f"Photos copied to: {photos_output_dir}")


def main():
    zip_dir = Path("downloaded_facebook_data")
    extract_dir = Path("extracted_data")
    output_dir = Path("website")
    
    print("Step 1: Extracting zip files...")
    json_files = extract_all_zips(zip_dir, extract_dir)
    
    print(f"\nStep 2: Processing {len(json_files)} JSON files...")
    posts = load_and_merge_posts(json_files)
    
    print(f"\nStep 3: Found {len(posts)} unique posts")
    
    print("\nStep 4: Generating CSV...")
    posts_to_csv(posts, Path("facebook_posts.csv"))
    
    print("\nStep 5: Generating HTML website...")
    generate_html(posts, extract_dir, output_dir)
    
    print(f"\nHotovo! Otvorte {output_dir / 'index.html'} v prehliadači.")


if __name__ == "__main__":
    main()
