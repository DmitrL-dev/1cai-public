// No host access, content scripts, permissions or network requests.
// Playwright evaluates tabs.setZoom/getZoom in this ephemeral worker.
chrome.runtime.onInstalled.addListener(() => {});
