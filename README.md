# Web Print

Web-based print & scan service for HP network printers.

## Features

- **Print**: Upload PDF, Word, Excel, PowerPoint, CSV, or images and print directly to HP printers via IPP protocol
- **Scan**: Scan documents from HP MFP printers via eSCL protocol (Platen only)
- **Preview**: In-browser PDF preview before printing
- **Page Selection**: Print specific pages (e.g., `1-3, 5, 8-10`)
- **Duplex**: Double-sided printing (long-edge / short-edge flip)
- **Orientation & Scaling**: Rotate and scale content before printing
- **Multi-location**: Select office location to auto-fill printer IP
- **File Conversion**: Automatically converts Word/Excel/PPT/CSV/images to PDF using LibreOffice and Pillow

## Requirements

- Python 3.10+
- LibreOffice (for Word/Excel/CSV conversion)
- HP printer with IPP support (port 443)

## Installation

```bash
# Clone
git clone git@github.com:chende556/web-print.git
cd web-print

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Configuration
cp config.example.py config.py
# Edit config.py with your printer IPs
```

### Install LibreOffice

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt install libreoffice-core libreoffice-calc libreoffice-writer -y
```

## Usage

```bash
python app.py
```

Open http://localhost:8000 in your browser.

## Configuration

Edit `config.py`:

```python
PRINTER_LOCATIONS = {
    "Office A": "10.0.0.1",
    "Office B": "10.0.0.2",
}
```

## Project Structure

```
├── app.py              # Flask web server (routes)
├── scanner.py          # eSCL scan interface
├── printer.py          # IPP print interface
├── converter.py        # File to PDF converter (Pillow + LibreOffice)
├── pdf_transform.py    # PDF rotation and scaling
├── pdf_merge.py        # Multi-page PDF merge
├── config.py           # Configuration (gitignored)
├── config.example.py   # Configuration template
├── requirements.txt    # Python dependencies
├── static/pdfjs/       # PDF.js for preview
└── templates/
    └── index.html      # Web UI
```

## Supported Printers

Tested with:
- HP LaserJet MFP M427dw (print + scan)
- HP Color LaserJet Pro M454nw (print only)

Should work with any HP printer that supports IPP over HTTPS.

## Notes

- Duplex printing requires `media` and `media-type` attributes in IPP request (HP firmware quirk)
- ADF scanning is not supported via eSCL on M427dw (returns 409 Conflict)
- Scan feature only works with MFP printers that expose `/eSCL/ScannerStatus`
- M454nw requires IPP authentication disabled in printer admin panel for printing

## License

MIT
