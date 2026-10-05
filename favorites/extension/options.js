import { check, cleanAddress, settings } from './faves.js';

const $ = (id) => document.getElementById(id);
const now = await settings();
$('address').value = now.address;
$('password').value = now.password;

function say(text, kind = '') { $('msg').textContent = text; $('msg').className = 'msg ' + kind; }

$('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const address = cleanAddress($('address').value);
  if (!address) return say("That doesn't look like an address. It's like http://100.101.102.103:8000", 'bad');
  $('address').value = address;
  // Ask Chrome for leave to talk to this one address -- and only this one.
  const granted = await chrome.permissions.request({ origins: [address + '/*'] });
  if (!granted) return say('Chrome needs your OK to talk to Faves at that address. Try again and choose Allow.', 'bad');
  let password = $('password').value.trim().replace(/^bearer\s+/i, '');
  $('password').value = password;
  await chrome.storage.local.set({ address, password });
  say('Checking…');
  try {
    const n = await check();
    say(`Connected ✓ ${n.toLocaleString()} saves in your Faves.`, 'good');
  } catch (err) {
    say(err.message, 'bad');
  }
});
