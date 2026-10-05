/* A synthetic walkthrough. No network requests, storage, analytics or product actions. */
(() => {
  'use strict';
  const tabs = Array.from(document.querySelectorAll('[role="tab"][data-step]'));
  const panels = Array.from(document.querySelectorAll('.demo-panel'));
  if (!tabs.length) return;
  const select = (tab, moveFocus = false) => {
    tabs.forEach(item => {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.classList.toggle('active', selected);
      item.tabIndex = selected ? 0 : -1;
    });
    panels.forEach(panel => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
    if (moveFocus) tab.focus();
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      // Preserve browser/page shortcuts such as Ctrl+Home and Alt+Left.
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      let next;
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); select(tabs[next], true); }
    });
  });
  const narrow = window.matchMedia('(max-width: 800px)');
  const updateOrientation = () => document.querySelector('[role="tablist"]').setAttribute('aria-orientation', narrow.matches ? 'horizontal' : 'vertical');
  updateOrientation();
  narrow.addEventListener('change', updateOrientation);
})();
