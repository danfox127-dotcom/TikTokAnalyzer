#!/usr/bin/env python3
"""
Social Media Forensic Analyzer
Analyzes TikTok and Instagram/Meta data exports to reveal how platforms profile you.
"""
import argparse
import json
import os
import sys
from parsers.tiktok import parse_tiktok_export
from parsers.instagram import parse_instagram_export
from report import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Analyze your social media data exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyzer.py --tiktok user_data_tiktok.json
  python analyzer.py --instagram ./instagram-export-folder/
  python analyzer.py --tiktok data.json --instagram ./ig-folder/ -o my_report.json
        """
    )
    parser.add_argument("--tiktok", help="Path to TikTok user_data_tiktok.json")
    parser.add_argument("--instagram", help="Path to Instagram export directory")
    parser.add_argument("-o", "--output", default="report.json", help="Output report path (default: report.json)")

    args = parser.parse_args()

    if not args.tiktok and not args.instagram:
        parser.error("Provide at least one: --tiktok or --instagram")

    tiktok_data = None
    instagram_data = None

    if args.tiktok:
        print(f"\n{'='*60}")
        print(f"  Parsing TikTok export: {args.tiktok}")
        print(f"{'='*60}")
        tiktok_data = parse_tiktok_export(args.tiktok)
        # Print summary stats
        ba = tiktok_data.get("behavioral_analysis", {})
        print(f"  Videos: {ba.get('total_videos', 0):,}")
        print(f"  Valid sessions: {ba.get('valid_sessions', 0):,}")
        print(f"  Skip rate: {ba.get('skip_rate', 0):.1f}%")
        print(f"  Linger rate: {ba.get('linger_rate', 0):.1f}%")
        print(f"  Night shift: {ba.get('night_shift_ratio', 0):.1f}%")
        print(f"  Searches: {len(tiktok_data.get('searches', []))}")
        print(f"  Likes: {len(tiktok_data.get('likes', []))}")
        print(f"  Unique IPs: {tiktok_data.get('login_history_stats', {}).get('unique_ips', 0)}")

    if args.instagram:
        print(f"\n{'='*60}")
        print(f"  Parsing Instagram export: {args.instagram}")
        print(f"{'='*60}")
        instagram_data = parse_instagram_export(args.instagram)
        print(f"  Ad categories assigned: {len(instagram_data.get('ad_categories', []))}")
        print(f"  Advertisers with your data: {instagram_data.get('advertiser_count', 0):,}")
        print(f"  Recommended topics: {len(instagram_data.get('recommended_topics', []))}")
        print(f"  Off-Meta trackers: {len(instagram_data.get('off_meta_activity', []))}")
        print(f"  Devices tracked: {len(instagram_data.get('devices', []))}")

    output_path = generate_report(tiktok_data, instagram_data, args.output)
    print(f"\n  Report saved to: {output_path}")
    print(f"  Open dashboard.html in a browser to visualize.\n")


if __name__ == "__main__":
    main()
