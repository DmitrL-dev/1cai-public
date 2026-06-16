/**
 * SUPER SIMPLE Support System
 * For owners who don't know tech
 */

import React from 'react';

interface Ticket {
  id: string;
  from: string;
  question: string;
  urgency: 'urgent' | 'normal';
}

const mockTickets: Ticket[] = [
  {
    id: '1',
    from: 'John from Acme Corp',
    question: 'How do I invite my team?',
    urgency: 'normal'
  },
  {
    id: '2',
    from: 'Sarah from Tech Solutions',
    question: 'Payment failed, help!',
    urgency: 'urgent'
  },
];

const quickReplies = [
  {
    title: '✅ "How to invite team"',
    template: "Hi! To invite your team:\n1. Click 'Team' button\n2. Click 'Invite'\n3. Enter email\n4. Done!\n\nNeed help? Just reply to this!"
  },
  {
    title: '💳 "Payment issue"',
    template: "Hi! Sorry about the payment issue. Let me check...\n\nI've reset your billing. Please try again or update your card.\n\nStill problems? Call me!"
  },
  {
    title: '❓ "How does it work"',
    template: "Hi! Our AI helps your developers work faster by:\n- Writing code automatically\n- Finding bugs early\n- Generating tests\n\nYou save time = save money!\n\nQuestions? I'm here!"
  },
  {
    title: '⬆️ "Want to upgrade"',
    template: "Great! Here are your options:\n\nStarter €99 → Professional €299\nOR\nProfessional €299 → Enterprise €999\n\nWhich interests you?"
  },
];

export const SupportSimple: React.FC = () => {
  const [selectedTicket, setSelectedTicket] = React.useState<string | null>(null);
  const [showTemplates, setShowTemplates] = React.useState(false);
  
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-4xl font-bold text-gray-900 mb-8">
        📞 Customer Support
      </h1>
      
      {/* TICKETS */}
      <div className="space-y-4 mb-8">
        {mockTickets.map((ticket) => (
          <div
            key={ticket.id}
            className={`bg-white rounded-2xl p-8 shadow-lg ${
              ticket.urgency === 'urgent' ? 'border-4 border-red-400' : ''
            }`}
          >
            {ticket.urgency === 'urgent' && (
              <div className="bg-red-100 text-red-800 px-4 py-2 rounded-xl inline-block mb-4 text-xl font-bold">
                🚨 URGENT!
              </div>
            )}
            
            <div className="mb-4">
              <p className="text-2xl font-bold text-gray-900 mb-2">
                From: {ticket.from}
              </p>
              <p className="text-xl text-gray-700 bg-gray-50 p-4 rounded-xl">
                "{ticket.question}"
              </p>
            </div>
            
            {/* QUICK REPLY BUTTONS */}
            {!selectedTicket && (
              <div>
                <p className="text-lg font-semibold mb-3">Quick replies:</p>
                <div className="grid grid-cols-2 gap-3">
                  {quickReplies.map((reply, index) => (
                    <button
                      key={index}
                      onClick={() => {
                        setSelectedTicket(ticket.id);
                        setShowTemplates(true);
                      }}
                      className="bg-blue-100 hover:bg-blue-200 text-blue-900 px-6 py-4 rounded-xl text-lg font-semibold text-left"
                    >
                      {reply.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
            
            {selectedTicket === ticket.id && showTemplates && (
              <div className="mt-4 bg-green-50 p-6 rounded-xl">
                <p className="text-lg font-semibold text-green-900 mb-3">
                  ✅ Reply sent!
                </p>
                <p className="text-gray-700">
                  Customer will receive your answer in 1 minute.
                </p>
                <button
                  onClick={() => {
                    setSelectedTicket(null);
                    setShowTemplates(false);
                  }}
                  className="mt-4 bg-green-600 text-white px-6 py-3 rounded-xl font-semibold"
                >
                  OK, Got it!
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* HELP */}
      <div className="bg-yellow-50 border-4 border-yellow-300 rounded-2xl p-8">
        <p className="text-2xl font-bold text-gray-900 mb-4">
          💡 Can't answer a question?
        </p>
        <p className="text-xl text-gray-700 mb-6">
          No problem! We can help.
        </p>
        
        <div className="flex gap-4">
          <button className="flex-1 bg-blue-500 hover:bg-blue-600 text-white px-8 py-6 rounded-xl text-xl font-bold">
            📧 Forward to Tech Support
          </button>
          <button className="flex-1 bg-purple-500 hover:bg-purple-600 text-white px-8 py-6 rounded-xl text-xl font-bold">
            ❓ Ask AI for Answer
          </button>
        </div>
      </div>
    </div>
  );
};

export default SupportSimple;


