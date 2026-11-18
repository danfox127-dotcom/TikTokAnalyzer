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

// Which save each notification opens. Kept in session storage, not in this
// worker's memory: Chrome stops an idle worker after about 30 seconds, and a
// click on the notification after that would otherwise do nothing.
function notify(title, message, link) {
  chrome.notifications.create({ type: 'basic', iconUrl: 'icons/icon-128.png', title, message: message || '' }, (id) => {
    if (link) chrome.storage.session.set({ ['open:' + id]: link });
  });
}
chrome.notifications.onClicked.addListener(async (id) => {
  const key = 'open:' + id;
  const { [key]: link } = await chrome.storage.session.get(key);
  if (link) {
    chrome.tabs.create({ url: link });
    chrome.storage.session.remove(key);
  }
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  keepAndTell(info.menuItemId === 'keep-link' ? info.linkUrl : (tab && tab.url) || info.pageUrl);
});

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== 'keep-tab') return;
  tab = tab || (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (tab && tab.url) keepAndTell(tab.url);
});
