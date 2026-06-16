/**
 * SUPER SIMPLE Customer List
 * Grandma-friendly interface
 */

import React from 'react';

interface Customer {
  id: string;
  name: string;
  paying: number;
  status: 'happy' | 'ok' | 'unhappy';
  since: string;
}

const mockCustomers: Customer[] = [
  { id: '1', name: 'Acme Corporation', paying: 299, status: 'happy', since: '3 months' },
  { id: '2', name: 'Tech Solutions', paying: 99, status: 'ok', since: '5 days (trial)' },
  { id: '3', name: 'Digital Services', paying: 999, status: 'happy', since: '1 year' },
];

export const CustomerListSimple: React.FC = () => {
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-4xl font-bold text-gray-900 mb-8">
        👥 Your Customers
      </h1>
      
      {/* TOTAL */}
      <div className="bg-white rounded-2xl p-8 mb-8 shadow-lg">
        <p className="text-6xl font-bold text-center text-gray-900">
          {mockCustomers.length}
        </p>
        <p className="text-2xl text-center text-gray-600 mt-2">
          companies use your product
        </p>
        
        <div className="mt-6 flex justify-center gap-8 text-xl">
          <div>
            <span className="text-3xl">😊</span>
            <span className="ml-2 font-semibold">30 happy</span>
          </div>
          <div>
            <span className="text-3xl">😐</span>
            <span className="ml-2">10 okay</span>
          </div>
          <div>
            <span className="text-3xl">😞</span>
            <span className="ml-2">2 unhappy</span>
          </div>
        </div>
      </div>
      
      {/* CUSTOMER CARDS (BIG AND SIMPLE) */}
      <div className="space-y-4">
        {mockCustomers.map((customer) => (
          <div
            key={customer.id}
            className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-4 mb-3">
                  {customer.status === 'happy' && <span className="text-5xl">😊</span>}
                  {customer.status === 'ok' && <span className="text-5xl">😐</span>}
                  {customer.status === 'unhappy' && <span className="text-5xl">😞</span>}
                  
                  <div>
                    <h3 className="text-3xl font-bold text-gray-900">
                      {customer.name}
                    </h3>
                    <p className="text-xl text-gray-600">
                      Paying €{customer.paying}/month
                    </p>
                  </div>
                </div>
                
                <p className="text-lg text-gray-500">
                  Customer for: {customer.since}
                </p>
              </div>
              
              {/* SIMPLE ACTIONS */}
              <div className="flex flex-col gap-3">
                <button className="bg-blue-500 hover:bg-blue-600 text-white px-8 py-4 rounded-xl text-lg font-semibold">
                  📧 Send Email
                </button>
                <button className="bg-green-500 hover:bg-green-600 text-white px-8 py-4 rounded-xl text-lg font-semibold">
                  📞 Call
                </button>
                <button className="bg-gray-200 hover:bg-gray-300 text-gray-900 px-8 py-4 rounded-xl text-lg font-semibold">
                  👁️ View Details
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* BIG ADD BUTTON */}
      <button className="mt-8 w-full bg-gradient-to-r from-purple-400 to-purple-600 hover:from-purple-500 hover:to-purple-700 text-white rounded-2xl p-8 text-2xl font-bold shadow-xl">
        ➕ Add New Customer Manually
      </button>
    </div>
  );
};

export default CustomerListSimple;


