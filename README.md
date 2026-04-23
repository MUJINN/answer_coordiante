# OCR Coordinate Visualization Toolkit

A toolkit for testing coordinate OCR workflows and visualizing OCR outputs on educational answer images. It supports both local-image and URL-based input modes and can generate HTML pages for batch review.

## What this project does

- Sends local images or image URLs into an OCR workflow
- Receives OCR results with coordinates
- Generates HTML visualizations with bounding boxes and grouped views
- Supports concurrent batch testing for large input sets

## Why it matters

This repository is a practical debugging and evaluation tool. It helps validate whether OCR outputs are usable in downstream education workflows that depend on answer coordinates.

## Main files

- `test_coordinate_ocr.py`: local image OCR test
- `test_coordinate_ocr_url.py`: URL-based OCR test
- `generate_batch_viewer.py`: batch HTML viewer for base64 image results
- `generate_batch_viewer_url.py`: batch HTML viewer for URL-based results
- `README_COORDINATE_OCR.md`: detailed usage guide

## Quick start

```bash
python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls_example.txt
```

Then use the viewer generator to inspect results visually.

## Key capabilities

- Coordinate OCR testing
- Local and remote image support
- Batch visualization
- Workflow debugging support

## Notes

This public repository is a cleaned release version. Large sample images, generated outputs, and local test artifacts were excluded.
