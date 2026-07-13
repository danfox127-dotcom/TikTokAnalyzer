/**
 * WP-1.1 engine port — video id extraction.
 * Mirrors `utils.oembed.extract_video_id`: pull the numeric id out of a
 * `/video/<id>` URL, else null. (The Python short-url expansion path is a
 * network concern that lives in the enrichment stage, not the stopwatch.)
 */
export function extractVideoId(url: string): string | null {
  if (!url) return null;
  const m = url.match(/\/video\/(\d+)/);
  return m ? m[1] : null;
}
