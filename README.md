# SYS.TEARDOWN -- Social Media Forensic Analyzer

A local-only forensic analysis tool that parses your TikTok and Instagram/Meta data exports to reveal exactly how these platforms profile, track, and categorize you. All processing happens on your machine -- no data ever leaves your computer.

## Get Your Data Exports

- **TikTok**: Settings > Privacy > Download Your Data > Request Data (JSON format). [TikTok Data Download](https://www.tiktok.com/setting/download-your-data)
- **Instagram/Meta**: Settings > Your Activity > Download Your Information > Request Download (JSON format). [Instagram Data Download](https://accountscenter.instagram.com/info_and_permissions/dyi/)

## Quick Start

```bash
# Analyze TikTok only
python analyzer.py --tiktok user_data_tiktok.json

# Analyze Instagram only
python analyzer.py --instagram ./instagram-export-folder/

# Analyze both platforms
python analyzer.py --tiktok user_data_tiktok.json --instagram ./instagram-folder/ -o report.json
```

Then open `dashboard.html` in your browser and load `report.json`.

## What It Reveals

- **Behavioral profiling**: Skip rates, linger patterns, night-shift usage, hourly activity heatmaps
- **Interest inference**: What TikTok and Meta think you care about
- **Ad targeting categories**: How Meta categorizes you for advertisers (income, demographics, behaviors)
- **Advertiser access**: Which companies have uploaded your data for ad targeting
- **Off-platform surveillance**: Third-party sites and apps reporting your activity back to Meta/TikTok
- **Device and location tracking**: Every device and IP address the platforms have logged
- **The transparency gap**: A side-by-side comparison of what each platform reveals vs. hides

## Requirements

Python 3.8+ (standard library only -- no pip installs needed).

## Privacy

All analysis runs locally in Python. The dashboard is a single HTML file that reads your report via the browser FileReader API. Nothing is uploaded, transmitted, or stored remotely.
