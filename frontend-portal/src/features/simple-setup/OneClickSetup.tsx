/**
 * ONE-CLICK SETUP
 * For people who hate technology
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export const OneClickSetup: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  
  const handleStart = async () => {
    setLoading(true);
    
    // Step 1: Creating your account...
    setStep(1);
    await sleep(2000);
    
    // Step 2: Setting up your workspace...
    setStep(2);
    await sleep(2000);
    
    // Step 3: Preparing AI assistants...
    setStep(3);
    await sleep(2000);
    
    // Done!
    setStep(4);
    await sleep(1000);
    
    // Redirect to dashboard
    navigate('/owner-dashboard');
  };
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50">
        <div className="text-center">
          <div className="text-8xl mb-8 animate-bounce">
            {step === 1 && '🔧'}
            {step === 2 && '🏗️'}
            {step === 3 && '🤖'}
            {step === 4 && '🎉'}
          </div>
          
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            {step === 1 && 'Creating your account...'}
            {step === 2 && 'Setting up your workspace...'}
            {step === 3 && 'Preparing AI assistants...'}
            {step === 4 && 'Done! Welcome aboard! 🎊'}
          </h2>
          
          <div className="w-64 h-4 bg-gray-200 rounded-full mx-auto">
            <div
              className="h-4 bg-green-500 rounded-full transition-all"
              style={{ width: `${(step / 4) * 100}%` }}
            />
          </div>
          
          <p className="text-gray-600 mt-4">
            {step < 4 ? 'Please wait...' : 'Redirecting...'}
          </p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50 p-4">
      <div className="max-w-2xl w-full">
        {/* BIG FRIENDLY GREETING */}
        <div className="text-center mb-12">
          <div className="text-9xl mb-6">🚀</div>
          <h1 className="text-6xl font-bold text-gray-900 mb-4">
            Welcome!
          </h1>
          <p className="text-3xl text-gray-700 mb-2">
            Start making money with AI
          </p>
          <p className="text-xl text-gray-600">
            in just 30 seconds
          </p>
        </div>
        
        {/* THE BIG BUTTON */}
        <div className="bg-white rounded-3xl shadow-2xl p-12 text-center">
          <p className="text-2xl text-gray-700 mb-8">
            Ready to start?
          </p>
          
          <button
            onClick={handleStart}
            className="bg-gradient-to-r from-green-400 to-green-600 hover:from-green-500 hover:to-green-700 text-white rounded-2xl px-16 py-8 text-4xl font-bold shadow-xl transform hover:scale-105 transition-all"
          >
            🎯 START NOW
          </button>
          
          <p className="text-gray-500 mt-6">
            ← Click this button. That's it! Nothing else!
          </p>
          
          <div className="mt-12 pt-8 border-t border-gray-200">
            <p className="text-lg text-gray-600 mb-4">What happens next:</p>
            <div className="space-y-3 text-left max-w-md mx-auto">
              <div className="flex items-center gap-3">
                <span className="text-2xl">✓</span>
                <span>We create your workspace (10 seconds)</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl">✓</span>
                <span>We activate AI assistants (10 seconds)</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl">✓</span>
                <span>You start making money (immediately!)</span>
              </div>
            </div>
          </div>
        </div>
        
        {/* TRUST INDICATORS */}
        <div className="mt-8 text-center text-gray-600">
          <p className="text-lg">✓ No credit card required</p>
          <p className="text-lg">✓ No installation needed</p>
          <p className="text-lg">✓ Cancel anytime</p>
        </div>
      </div>
    </div>
  );
};

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export default OneClickSetup;


