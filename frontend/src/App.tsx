import React, { useState } from 'react';
import RadarView from './components/RadarView';
import ProfileView from './components/ProfileView';
import CoachingView from './components/CoachingView';
import InGameView from './components/InGameView';
import MetaBuildsView from './components/MetaBuildsView';
import SimuladorView from './components/SimuladorView';
import TierListBansView from './components/TierListBansView';

// Lista de pestañas según la imagen original
const TABS = [
  { id: 'perfil', label: 'MI PERFIL', icon: '👤' },
  { id: 'coaching', label: 'COACHING PRO', icon: '🎓' },
  { id: 'radar', label: 'RADAR EN VIVO', icon: '📡' },
  { id: 'ingame', label: 'IN-GAME', icon: '🎮' },
  { id: 'meta', label: 'META_BUILDS', icon: '📊' },
  { id: 'simulador', label: 'SIMULADOR 1V1', icon: '🤖' },
  { id: 'tierlist', label: 'TIER LIST DE BANS', icon: '🚫' },
];

function App() {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('nexus_activeTab') || 'perfil';
  });

  const handleTabChange = (id: string) => {
    setActiveTab(id);
    localStorage.setItem('nexus_activeTab', id);
  };

  return (
    <div className="flex flex-col h-screen bg-bgDark text-textWhite font-sans overflow-hidden">
      
      {/* Top Header / Title Bar */}
      <div className="flex items-center justify-between px-6 pt-4 pb-2 bg-bgDark">
        <div className="w-1/3"></div> {/* Spacer para centrar el título */}
        
        <div className="w-1/3 flex justify-center">
          <h1 className="text-3xl font-extrabold text-accentRed tracking-widest" style={{ textShadow: '0 0 10px rgba(230,57,70,0.5)' }}>
            LOL ESPORTS ANALYTICS
          </h1>
        </div>
        
        {/* Toggles top right */}
        <div className="w-1/3 flex justify-end items-center space-x-4">
          <div className="flex items-center space-x-2 bg-bgPanel px-3 py-1.5 rounded border border-borderSubtle">
            <div className="w-3 h-3 rounded-full bg-borderSubtle"></div>
            <span className="text-xs text-textMuted font-bold">IN-GAME</span>
          </div>
          <div className="flex items-center space-x-2 bg-bgPanel px-3 py-1.5 rounded border border-borderSubtle">
            <div className="w-3 h-3 rounded-full bg-accentTeal shadow-[0_0_8px_rgba(45,212,191,0.6)]"></div>
            <span className="text-xs text-textWhite font-bold">OVERLAY</span>
          </div>
        </div>
      </div>
      
      {/* Horizontal Navigation Menu */}
      <div className="border-b border-borderSubtle bg-bgDark px-8">
        <nav className="flex justify-center space-x-8">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`py-4 px-2 flex items-center space-x-2 text-sm font-semibold transition-colors relative ${
                activeTab === tab.id 
                  ? 'text-accentRed' 
                  : 'text-textMuted hover:text-textWhite'
              }`}
            >
              <span className="text-xs opacity-70">{tab.icon}</span>
              <span className="tracking-wide">{tab.label}</span>
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 w-full h-[2px] bg-accentRed shadow-[0_0_8px_rgba(230,57,70,0.8)]"></div>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-6 bg-[#05080f] overflow-y-auto">
        <div className="max-w-[1400px] mx-auto h-full">
          {activeTab === 'radar' && <RadarView />}
          {activeTab === 'perfil' && <ProfileView />}
          {activeTab === 'coaching' && <CoachingView />}
          {activeTab === 'ingame' && <InGameView />}
          {activeTab === 'meta' && <MetaBuildsView />}
          {activeTab === 'simulador' && <SimuladorView />}
          {activeTab === 'tierlist' && <TierListBansView />}
        </div>
      </div>
      
    </div>
  );
}

export default App;
