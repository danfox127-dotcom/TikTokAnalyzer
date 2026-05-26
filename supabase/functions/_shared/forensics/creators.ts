/**
 * Creator Registry & Automated Vibe Detection (TypeScript Port)
 */

export const CREATOR_REGISTRY: Record<string, [string, string, number]> = {
  // Sports
  "chelseafc": ["sports", "The Dedicated Fan", 1.0],
  "premierleague": ["sports", "The Global Spectator", 1.0],
  "nba": ["sports", "The Courtside Analyst", 1.0],
  "masonmount": ["sports", "The Player Tracker", 0.9],
  "reece_james": ["sports", "The Player Tracker", 0.9],

  // Local Life / NYC
  "brooklyn.beckham": ["fashion", "The Lifestyle Observer", 0.5],
  "newyorkcity": ["local_life", "The Urban Resident", 0.8],
  "timeoutnewyork": ["local_life", "The City Curator", 0.9],

  // Parenting
  "uppababy": ["parenting", "The Gear Researcher", 1.0],
  "disney": ["parenting", "The Family Entertainer", 0.7],

  // Tech / Productivity
  "cursor_ai": ["tech", "The AI Optimizer", 1.0],
  "firebase": ["tech", "The Backend Architect", 1.0],
  "marquesbrownlee": ["tech", "The Gadget Guru", 1.0],

  // Humor
  "khaby.lame": ["humor", "The Silent Reactant", 0.9],
};

export function getCreatorMeta(handle: string) {
  const cleanHandle = handle.toLowerCase().replace(/^@/, "");
  if (cleanHandle in CREATOR_REGISTRY) {
    const [genre, archetype, confidence] = CREATOR_REGISTRY[cleanHandle];
    return { handle, genre, archetype, confidence };
  }
  return null;
}

export function resolveVibeCluster(vibeCluster: any[]) {
  return vibeCluster.map(entry => {
    const meta = getCreatorMeta(entry.handle || "");
    if (meta) {
      return { ...entry, ...meta };
    }
    return { ...entry, genre: "unknown", archetype: "unknown", confidence: 0 };
  });
}
