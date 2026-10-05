// Right-click "Keep in Faves", and the keyboard shortcut.
import { keep, itemUrl } from './faves.js';

chrome.runtime.onInstalled.addListener((details) => {
  chrome.contextMenus.create({ id: 'keep-link', title: 'Keep link in Faves', contexts: ['link'] });
  chrome.contextMenus.create({ id: 'keep-page', title: 'Keep this page in Faves', contexts: ['page', 'video', 'image'] });
  if (details.reason === 'install') chrome.runtime.openOptionsPage();
});

async function keepAndTell(url) {
  try {
    const r = await keep(url);
    notify(r.created ? 'Kept ✓' : 'Already in Faves ✓', r.title || url, await itemUrl(r.id));
  } catch (e) {
    notify("Couldn't keep that", e.message);
  }
}

const opened = new Map();
function notify(title, message, link) {
  chrome.notifications.create({ type: 'basic', iconUrl: 'icons/icon-128.png', title, message: message || '' }, (id) => {
    if (link) opened.set(id, link);
  });
}
chrome.notifications.onClicked.addListener((id) => {
  if (opened.has(id)) chrome.tabs.create({ url: opened.get(id) });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  keepAndTell(info.menuItemId === 'keep-link' ? info.linkUrl : (tab && tab.url) || info.pageUrl);
});

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== 'keep-tab') return;
  tab = tab || (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (tab && tab.url) keepAndTell(tab.url);
});
