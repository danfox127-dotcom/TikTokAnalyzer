// Talking to your Faves library: where it is, and keeping a link there.

export async function settings() {
  const { address = '', password = '' } = await chrome.storage.local.get(['address', 'password']);
  return { address: address.replace(/\/+$/, ''), password };
}

/** "http://100.101.102.103:8000" from whatever was typed: no path, no slash. */
export function cleanAddress(typed) {
  let a = (typed || '').trim();
  if (!a) return '';
  if (!/^https?:\/\//i.test(a)) a = 'http://' + a;
  try { return new URL(a).origin; } catch { return ''; }
}

function headers(password) {
  const h = { 'Content-Type': 'application/json' };
  if (password) h.Authorization = 'Bearer ' + password;
  return h;
}

/** Plain-words reasons, for the person rather than the console. */
export class FavesError extends Error {}

async function call(path, init = {}) {
  const { address, password } = await settings();
  if (!address) throw new FavesError('Set up Faves first: add its address in the options.');
  let res;
  try {
    res = await fetch(address + path, { ...init, headers: headers(password) });
  } catch {
    throw new FavesError("Can't reach Faves. Is the Mac on, with the Faves window open (and Tailscale on, if you're away)?");
  }
  if (res.status === 401) throw new FavesError("Faves didn't accept the password. Check it in the options.");
  if (res.status === 400) throw new FavesError("There's no link here Faves can keep.");
  if (!res.ok) throw new FavesError(`Faves had a problem (${res.status}). Try again in a moment.`);
  return res.json();
}

/** Keep a link. Returns {id, created, title, ...} as /save does. */
export function keep(url, note = '') {
  return call('/save', { method: 'POST', body: JSON.stringify(note ? { url, note } : { url }) });
}

/** Can we reach it, and does it take the password? Returns the number of saves. */
export async function check() {
  const health = await call('/healthz');
  await call('/collections.json');  // needs the password, when one is set
  return health.items;
}

export async function itemUrl(id) {
  const { address } = await settings();
  return `${address}/item/${id}`;
}
