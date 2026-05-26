import { parseTiktokData } from "./supabase/functions/_shared/forensics/tiktok_parser.ts";
import { buildGhostProfile } from "./supabase/functions/_shared/forensics/ghost_profile.ts";

async function test() {
  try {
    const text = await Deno.readTextFile("../../Project Guidance for LLMs/user_data_tiktok.json");
    const rawData = JSON.parse(text);
    
    console.log("Parsing TikTok Data...");
    const parsed = parseTiktokData(rawData);
    
    console.log("Building Ghost Profile...");
    const profile = buildGhostProfile(parsed);
    
    console.log("\n--- FORENSIC RESULTS ---");
    console.log("Archetype:", profile.primary_archetype.name);
    console.log("Conscious Videos:", profile.stopwatch_metrics.total_conscious_videos);
    console.log("Linger Rate:", profile.behavioral_nodes.linger_rate_percentage + "%");
    console.log("Night Shift:", profile.behavioral_nodes.night_shift_ratio + "%");
    
    if (profile.interest_clusters && profile.interest_clusters.length > 0) {
      console.log("\nTop Interests:");
      profile.interest_clusters.slice(0, 5).forEach((c: any) => console.log(`- ${c.term} (${c.count})`));
    }

    if (profile.interest_phrases && profile.interest_phrases.length > 0) {
      console.log("\nTop Phrases:");
      profile.interest_phrases.slice(0, 5).forEach((p: any) => console.log(`- "${p.phrase}" (${p.count})`));
    }

  } catch (e) {
    console.error("Test Failed:", e.message);
  }
}

test();
