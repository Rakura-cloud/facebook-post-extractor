# Facebook Posts Extractor

Extracts posts and photos from Facebook data export into CSV and HTML website.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

1. Download your Facebook data and place zip files in `downloaded_facebook_data/` folder

2. Run the extractor:

```bash
uv run main.py
```

## Output

- `facebook_posts.csv` - All posts with text, photos, tags, and links
- `website/index.html` - Simple HTML viewer for browsing posts
- `website/photos/` - All photos from posts
# facebook-post-extractor
