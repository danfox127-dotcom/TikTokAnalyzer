
import json
import sys
import os
from parsers.tiktok import parse_tiktok_export
from api.ghost_profile import build_ghost_profile
from api.narratives import build_narrative_blocks

def main():
    file_path = "../Documents/Project Guidance for LLMs/user_data_tiktok.json"
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"--- Parsing Data from {file_path} ---")
    try:
        parsed = parse_tiktok_export(file_path)
        print(f"DEBUG: login_history count: {len(parsed.get('login_history', []))}")
        print(f"DEBUG: watch_history_active count: {len(parsed.get('watch_history_active', []))}")
        print(f"DEBUG: ad_interests count: {len(parsed.get('ad_interests', []))}")
        if parsed.get('login_history'):
            print(f"DEBUG: First login entry: {parsed['login_history'][0]}")
    except Exception as e:
        print(f"Error parsing file: {e}")
        return

    print(f"--- Building Ghost Profile ---")
    try:
        profile = build_ghost_profile(parsed)
    except Exception as e:
        print(f"Error building profile: {e}")
        return

    print(f"--- Generating Narrative Blocks (Deterministic Fallback) ---")
    try:
        blocks = build_narrative_blocks(profile, parsed)
    except Exception as e:
        print(f"Error building narrative blocks: {e}")
        return

    # Output Summary
    print("\n" + "="*50)
    print("FORENSIC DOSSIER SUMMARY")
    print("="*50)
    print(f"Primary Archetype: {profile['primary_archetype']['name']}")
    print(f"Cognitive Dissonance: {profile['primary_archetype']['dissonance']['label'] or 'None Detected'}")
    
    print("\n--- Key Metrics ---")
    bn = profile['behavioral_nodes']
    print(f"Skip Rate: {bn['skip_rate_percentage']}%")
    print(f"Linger Rate: {bn['linger_rate_percentage']}%")
    print(f"Night Shift Ratio: {bn['night_shift_ratio']}%")
    print(f"Social Graph: {bn['social_graph_followed_pct']}% Followed / {bn['social_graph_algorithmic_pct']}% Algorithmic")

    print("\n--- Top Creators (Vibe Cluster) ---")
    for creator in profile['creator_entities']['vibe_cluster'][:5]:
        print(f"- {creator['handle']}: {creator.get('genre', 'unknown')} / {creator.get('archetype', 'unknown')} ({creator['linger_count']} lingers)")

    print("\n--- Narrative Blocks ---")
    for block in blocks:
        print(f"\n[{block['icon']} {block['title']}]")
        print(block['prose'])

    # Save full output for inspection if needed
    with open("test_result_summary.json", "w") as f:
        json.dump(profile, f, indent=2)
    print(f"\nFull profile saved to test_result_summary.json")

if __name__ == "__main__":
    main()
