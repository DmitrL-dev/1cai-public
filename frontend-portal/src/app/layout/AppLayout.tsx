/**
 * App Layout
 * Main shell with sidebar and top navigation
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNav from './TopNav';
import { useAppStore } from '@/lib/store';
import { clsx } from 'clsx';

export const AppLayout: React.FC = () => {
  const { sidebarCollapsed } = useAppStore();
  
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <div className={clsx(
        'flex-1 flex flex-col transition-all',
        sidebarCollapsed ? 'ml-20' : 'ml-64'
      )}>
        {/* Top Navigation */}
        <TopNav />
        
        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppLayout;


