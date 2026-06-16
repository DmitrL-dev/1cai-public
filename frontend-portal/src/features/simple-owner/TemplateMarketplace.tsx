/**
 * Template Marketplace
 * Click to activate, no configuration!
 */

import React, { useState } from 'react';

interface Template {
  id: string;
  name: string;
  description: string;
  benefit: string;
  icon: string;
  active: boolean;
}

const templates: Template[] = [
  {
    id: 'auto-review',
    name: 'Automatic Code Review',
    description: 'Check all code automatically',
    benefit: 'Find bugs before customers do',
    icon: '🔍',
    active: false
  },
  {
    id: 'test-gen',
    name: 'Test Generator',
    description: 'Create tests for your code',
    benefit: 'Save 5 hours/week',
    icon: '🧪',
    active: false
  },
  {
    id: 'weekly-report',
    name: 'Weekly Business Report',
    description: 'Get email every Monday',
    benefit: 'Know how business is doing',
    icon: '📊',
    active: false
  },
  {
    id: 'customer-welcome',
    name: 'Welcome New Customers',
    description: 'Auto-send welcome email',
    benefit: 'Great first impression',
    icon: '👋',
    active: false
  },
];

export const TemplateMarketplace: React.FC = () => {
  const [items, setItems] = useState(templates);
  
  const toggle = (id: string) => {
    setItems(items.map(item =>
      item.id === id ? { ...item, active: !item.active } : item
    ));
  };
  
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">
        ⚡ Ready-to-Use Tools
      </h1>
      <p className="text-2xl text-gray-600 mb-8">
        Click to activate. That's it!
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {items.map((template) => (
          <div
            key={template.id}
            className={`rounded-2xl p-8 shadow-lg transition-all ${
              template.active
                ? 'bg-gradient-to-br from-green-400 to-green-600 text-white'
                : 'bg-white'
            }`}
          >
            <div className="text-6xl mb-4">{template.icon}</div>
            
            <h3 className={`text-2xl font-bold mb-3 ${
              template.active ? 'text-white' : 'text-gray-900'
            }`}>
              {template.name}
            </h3>
            
            <p className={`text-lg mb-4 ${
              template.active ? 'text-white' : 'text-gray-700'
            }`}>
              {template.description}
            </p>
            
            <div className={`p-4 rounded-xl mb-6 ${
              template.active ? 'bg-white bg-opacity-20' : 'bg-blue-50'
            }`}>
              <p className={`text-lg font-semibold ${
                template.active ? 'text-white' : 'text-blue-900'
              }`}>
                ✨ {template.benefit}
              </p>
            </div>
            
            <button
              onClick={() => toggle(template.id)}
              className={`w-full py-4 rounded-xl text-xl font-bold transition-all ${
                template.active
                  ? 'bg-white text-green-600 hover:bg-gray-100'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
            >
              {template.active ? '✓ ACTIVE - Click to Turn Off' : '▶ Click to Activate'}
            </button>
            
            {template.active && (
              <p className="text-center text-white mt-4 text-lg">
                ✅ Working! Your {template.name.toLowerCase()} is running.
              </p>
            )}
          </div>
        ))}
      </div>
      
      {/* MORE COMING SOON */}
      <div className="mt-8 bg-white rounded-2xl p-8 shadow-lg text-center">
        <p className="text-3xl mb-3">🎁</p>
        <p className="text-2xl font-bold text-gray-900 mb-2">
          More tools coming soon!
        </p>
        <p className="text-lg text-gray-600">
          We add new tools every month. They all work with one click!
        </p>
      </div>
    </div>
  );
};

export default TemplateMarketplace;


