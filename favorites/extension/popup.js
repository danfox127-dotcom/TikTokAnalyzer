import { keep, itemUrl, settings } from './faves.js';

const $ = (id) => document.getElementById(id);
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
$('title').textContent = (tab && tab.title) || 'This page';
$('url').textContent = tab && tab.url ? new URL(tab.url).hostname.replace(/^www\./, '') : '';
$('settings').addEventListener('click', (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); });

if (!(await settings()).address) {
  say("First, tell the extension where Faves is.", 'bad');
  $('keep').textContent = 'Set up Faves';
  $('keep').addEventListener('click', () => chrome.runtime.openOptionsPage());
} else {
  $('note').focus();
  $('keep').addEventListener('click', go);
  $('note').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) go(); });
}

function say(text, kind = '') { $('msg').textContent = text; $('msg').className = 'msg ' + kind; }

async function go() {
  $('keep').disabled = true; $('keep').textContent = 'Keeping…'; say('');
  try {
    const r = await keep(tab.url, $('note').value.trim());
    $('keep').textContent = r.created ? 'Kept ✓' : 'Already kept ✓';
    $('keep').classList.add('done');
    // Until Faves has looked the link up, its "title" is just the link.
    const title = r.title && r.title !== tab.url ? r.title : tab.title;
    say(title ? `“${title}” is in your library.` : 'In your library.', 'good');
    const link = await itemUrl(r.id);
    $('open').hidden = false;
    $('open').onclick = (e) => { e.preventDefault(); chrome.tabs.create({ url: link }); };
  } catch (e) {
    $('keep').disabled = false; $('keep').textContent = 'Try again';
    say(e.message, 'bad');
  }
}
