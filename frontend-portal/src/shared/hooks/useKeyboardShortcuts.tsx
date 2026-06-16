/**
 * Keyboard Shortcuts Hook
 * Iteration 2 Quick Win #4: Power user productivity
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

type ShortcutHandler = (event: KeyboardEvent) => void;

interface Shortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;  // Cmd on Mac
  handler: ShortcutHandler;
}

const shortcuts: Shortcut[] = [
  // Navigation
  {
    key: 'k',
    meta: true,  // Cmd+K or Ctrl+K
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // Open search modal
      document.getElementById('global-search')?.focus();
    }
  },
  {
    key: 'p',
    meta: true,
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // Go to projects
      window.location.href = '/projects';
    }
  },
  {
    key: 'd',
    meta: true,
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // Go to dashboard
      window.location.href = '/';
    }
  },
  {
    key: 's',
    meta: true,
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // Go to settings
      window.location.href = '/settings';
    }
  },
  
  // Actions
  {
    key: 'n',
    meta: true,
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // New project
      const newButton = document.querySelector('[data-action="new-project"]');
      if (newButton) (newButton as HTMLElement).click();
    }
  },
  
  // UI
  {
    key: '/',
    handler: (e) => {
      e.preventDefault();
      // Focus search
      document.getElementById('global-search')?.focus();
    }
  },
  {
    key: 'Escape',
    handler: () => {
      // Close modals
      const modal = document.querySelector('[role="dialog"]');
      if (modal) {
        const closeButton = modal.querySelector('[aria-label="Close"]');
        if (closeButton) (closeButton as HTMLElement).click();
      }
    }
  },
  
  // Theme
  {
    key: 't',
    meta: true,
    ctrl: true,
    handler: (e) => {
      e.preventDefault();
      // Toggle dark mode
      const themeButton = document.querySelector('[aria-label="Toggle dark mode"]');
      if (themeButton) (themeButton as HTMLElement).click();
    }
  },
];

export const useKeyboardShortcuts = () => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const matchesKey = event.key === shortcut.key;
        const matchesCtrl = !shortcut.ctrl || event.ctrlKey;
        const matchesShift = !shortcut.shift || event.shiftKey;
        const matchesAlt = !shortcut.alt || event.altKey;
        const matchesMeta = !shortcut.meta || event.metaKey;
        
        if (matchesKey && matchesCtrl && matchesShift && matchesAlt && matchesMeta) {
          shortcut.handler(event);
          break;
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);
};

// Keyboard shortcuts help modal
export const KeyboardShortcutsHelp = () => {
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const modKey = isMac ? '⌘' : 'Ctrl';
  
  const shortcutsList = [
    { keys: `${modKey} + K`, description: 'Open search' },
    { keys: `${modKey} + P`, description: 'Go to projects' },
    { keys: `${modKey} + D`, description: 'Go to dashboard' },
    { keys: `${modKey} + S`, description: 'Go to settings' },
    { keys: `${modKey} + N`, description: 'New project' },
    { keys: `${modKey} + T`, description: 'Toggle dark mode' },
    { keys: '/', description: 'Focus search' },
    { keys: 'Esc', description: 'Close modal' },
  ];
  
  return (
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">Keyboard Shortcuts</h3>
      <div className="space-y-2">
        {shortcutsList.map((shortcut, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
            <span className="text-sm">{shortcut.description}</span>
            <kbd className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">
              {shortcut.keys}
            </kbd>
          </div>
        ))}
      </div>
      
      <p className="text-xs text-gray-500 mt-4">
        Press ? to show this help
      </p>
    </div>
  );
};


