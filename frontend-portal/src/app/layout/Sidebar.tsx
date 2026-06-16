/**
 * Sidebar Navigation
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  LayoutDashboard,
  FolderKanban,
  Code2,
  Users,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useAppStore, useAuthStore } from '@/lib/store';

export const Sidebar: React.FC = () => {
  const { sidebarCollapsed, toggleSidebar } = useAppStore();
  const { user } = useAuthStore();
  
  // Role-based navigation items
  const navItems = React.useMemo(() => {
    const items = [];
    
    switch (user?.role) {
      case 'executive':
        items.push(
          { path: '/executive', icon: LayoutDashboard, label: 'Dashboard' },
          { path: '/projects', icon: FolderKanban, label: 'Projects' },
          { path: '/analytics', icon: FileText, label: 'Analytics' }
        );
        break;
      
      case 'pm':
        items.push(
          { path: '/pm', icon: LayoutDashboard, label: 'Dashboard' },
          { path: '/projects', icon: FolderKanban, label: 'Projects' },
          { path: '/team', icon: Users, label: 'Team' },
          { path: '/sprints', icon: FileText, label: 'Sprints' }
        );
        break;
      
      case 'developer':
        items.push(
          { path: '/developer', icon: Code2, label: 'Console' },
          { path: '/projects', icon: FolderKanban, label: 'Projects' },
          { path: '/code-review', icon: FileText, label: 'Reviews' }
        );
        break;
      
      default:
        items.push(
          { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' }
        );
    }
    
    // Common items
    items.push(
      { path: '/settings', icon: Settings, label: 'Settings' }
    );
    
    return items;
  }, [user?.role]);
  
  return (
    <aside
      className={clsx(
        'fixed left-0 top-0 h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all z-10',
        sidebarCollapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-gray-200 dark:border-gray-700">
        {!sidebarCollapsed && (
          <span className="text-xl font-bold text-primary-500">
            1C AI
          </span>
        )}
        
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Toggle sidebar"
        >
          {sidebarCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>
      
      {/* Navigation */}
      <nav className="p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary-50 dark:bg-primary-900 text-primary-600 dark:text-primary-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              )
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && (
              <span className="font-medium">{item.label}</span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;


