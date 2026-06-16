/**
 * SUPER SIMPLE Owner Dashboard
 * For non-technical business owners
 * 
 * Rules:
 * - NO technical terms
 * - BIG numbers
 * - GREEN/RED only (simple!)
 * - ONE button per action
 * - Plain language
 */

import React from 'react';

export const OwnerDashboard: React.FC = () => {
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      {/* Greeting */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">
          Good Morning, Boss! 👋
        </h1>
        <p className="text-xl text-gray-600 mt-2">
          Here's your business in 30 seconds
        </p>
      </div>
      
      {/* THE MOST IMPORTANT NUMBER */}
      <div className="bg-gradient-to-r from-green-400 to-green-600 rounded-3xl p-12 mb-8 text-white shadow-2xl">
        <p className="text-2xl mb-2">💰 You Made This Month:</p>
        <p className="text-7xl font-bold mb-4">€12,450</p>
        <p className="text-2xl">
          ↗️ That's <span className="font-bold">+€1,630 more</span> than last month!
        </p>
      </div>
      
      {/* SIMPLE STATUS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Is Everything OK? */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">🟢</div>
          <p className="text-2xl font-bold text-gray-900 mb-2">Everything is OK</p>
          <p className="text-gray-600">All systems working fine</p>
        </div>
        
        {/* Customers */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">👥</div>
          <p className="text-5xl font-bold text-gray-900 mb-2">42</p>
          <p className="text-gray-600">Happy customers</p>
          <p className="text-green-600 font-semibold mt-2">+7 this month!</p>
        </div>
        
        {/* Growth */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">📈</div>
          <p className="text-5xl font-bold text-gray-900 mb-2">+23%</p>
          <p className="text-gray-600">Business growth</p>
          <p className="text-green-600 font-semibold mt-2">You're growing!</p>
        </div>
      </div>
      
      {/* WHAT HAPPENED TODAY */}
      <div className="bg-white rounded-2xl p-8 shadow-lg mb-8">
        <h2 className="text-2xl font-bold mb-6">📋 What Happened Today?</h2>
        
        <div className="space-y-4">
          <div className="flex items-center gap-4 p-4 bg-green-50 rounded-xl">
            <div className="text-3xl">✅</div>
            <div>
              <p className="font-semibold">New customer signed up!</p>
              <p className="text-gray-600">Tech Solutions Inc. - €299/month</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 p-4 bg-blue-50 rounded-xl">
            <div className="text-3xl">💬</div>
            <div>
              <p className="font-semibold">2 support messages</p>
              <p className="text-gray-600">
                <button className="text-blue-600 hover:underline">Click here to reply</button>
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 p-4 bg-purple-50 rounded-xl">
            <div className="text-3xl">🎉</div>
            <div>
              <p className="font-semibold">Your product helped developers save 47 hours today!</p>
              <p className="text-gray-600">That's €1,880 in value!</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* ONE-CLICK ACTIONS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <button className="bg-blue-500 hover:bg-blue-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105">
          <div className="text-4xl mb-3">📊</div>
          <p className="text-2xl font-bold mb-2">See Full Report</p>
          <p className="text-blue-100">Revenue, customers, everything →</p>
        </button>
        
        <button className="bg-purple-500 hover:bg-purple-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105">
          <div className="text-4xl mb-3">👥</div>
          <p className="text-2xl font-bold mb-2">My Customers</p>
          <p className="text-purple-100">See who's using your product →</p>
        </button>
        
        <button className="bg-green-500 hover:bg-green-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105">
          <div className="text-4xl mb-3">💳</div>
          <p className="text-2xl font-bold mb-2">Get Paid</p>
          <p className="text-green-100">Invoices, payments, money →</p>
        </button>
        
        <button className="bg-orange-500 hover:bg-orange-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105">
          <div className="text-4xl mb-3">📞</div>
          <p className="text-2xl font-bold mb-2">Customer Support</p>
          <p className="text-orange-100">Answer customer questions →</p>
        </button>
      </div>
      
      {/* HELP BUTTON (always visible) */}
      <button className="fixed bottom-8 right-8 bg-yellow-400 hover:bg-yellow-500 text-gray-900 rounded-full p-6 shadow-2xl text-2xl font-bold">
        ❓ HELP
      </button>
    </div>
  );
};

export default OwnerDashboard;


