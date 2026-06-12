import React, { useState, useEffect } from 'react';

interface PlayerData {
  summonerName: string;
  championName: string;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  items: { id: number; name: string }[];
}

interface InGameState {
  isActive: boolean;
  isLoading?: boolean;
  gameTime?: number;
  blueTeam?: PlayerData[];
  redTeam?: PlayerData[];
  compBlue?: { ad: number; ap: number; tanks: number };
  compRed?: { ad: number; ap: number; tanks: number };
}

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const InGameView: React.FC = () => {
  const [state, setState] = useState<InGameState>({ isActive: false });

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: any;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws/ingame');
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(data);
        } catch (e) {
          console.error("Error parsing ingame msg", e);
        }
      };

      ws.onclose = () => {
        setState({ isActive: false });
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  if (!state.isActive) {
    return (
      <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2 pb-6 justify-center items-center">
        <div className="flex flex-col items-center justify-center py-8">
          <div className="flex items-center space-x-2 text-[#8b5cf6] font-bold text-lg mb-2">
            <span>🎮</span>
            <span>Esperando partida...</span>
          </div>
          <div className="text-[#475569] text-sm">
            Los datos apareceran cuando entres a la Grieta
          </div>
        </div>
      </div>
    );
  }

  if (state.isLoading) {
    return (
      <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2 pb-6 justify-center items-center">
        <div className="w-16 h-16 border-4 border-[#8b5cf6] border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-[#94a3b8] font-bold tracking-widest text-lg">ENTRANDO A LA GRIETA...</p>
      </div>
    );
  }

  const renderPlayer = (p: PlayerData, isBlue: boolean) => {
    const csPerMin = state.gameTime ? (p.cs / (state.gameTime / 60)).toFixed(1) : "0.0";
    
    return (
      <div key={p.summonerName} className="grid grid-cols-12 gap-2 p-3 border-b border-[#1e293b] hover:bg-[#1e293b] transition duration-200">
        
        {/* CHAMPION */}
        <div className="col-span-4 flex items-center space-x-3 overflow-hidden">
          <img 
            src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${p.championName}.png`}
            className={`w-10 h-10 rounded shadow-sm border-2 ${isBlue ? 'border-[#3b82f6]' : 'border-[#ef4444]'}`}
            alt={p.championName}
          />
          <div className="flex flex-col overflow-hidden">
            <span className="font-bold text-[#e2e8f0] truncate">{p.championName}</span>
            <span className="text-[10px] text-[#64748b] truncate">{p.summonerName}</span>
          </div>
        </div>

        {/* KDA */}
        <div className="col-span-2 flex items-center justify-center font-black text-[#e2e8f0] text-sm">
          <span className="text-[#10b981]">{p.kills}</span>
          <span className="mx-1 text-[#64748b]">/</span>
          <span className="text-[#ef4444]">{p.deaths}</span>
          <span className="mx-1 text-[#64748b]">/</span>
          <span className="text-[#38bdf8]">{p.assists}</span>
        </div>

        {/* CS */}
        <div className="col-span-2 flex flex-col items-center justify-center">
          <span className="font-bold text-[#e2e8f0] text-sm">{p.cs}</span>
          <span className="text-[10px] text-[#64748b]">{csPerMin}/min</span>
        </div>

        {/* ITEMS */}
        <div className="col-span-4 flex items-center justify-start space-x-1 overflow-x-auto custom-scrollbar">
          {p.items.map((it, idx) => (
            <img 
              key={idx}
              src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/item/${it.id}.png`}
              className="w-6 h-6 rounded border border-[#334155]"
              title={it.name}
              alt={it.name}
            />
          ))}
        </div>
      </div>
    );
  };

  const compB = state.compBlue || { ad: 0, ap: 0, tanks: 0 };
  const compR = state.compRed || { ad: 0, ap: 0, tanks: 0 };

  return (
    <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2 pb-6">
      
      {/* 1. TOP HEADER: TIMER */}
      <div className="flex flex-col items-center justify-center py-4 mb-2">
        <div className="text-[#38bdf8] font-black text-4xl tracking-widest drop-shadow-lg">
          {formatTime(state.gameTime || 0)}
        </div>
        <div className="text-[#64748b] text-xs font-bold uppercase tracking-[0.3em] mt-1">
          Tiempo de Partida
        </div>
      </div>

      {/* 2. MAIN CONTENT: TEAM TABLES */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        
        {/* LEFT COLUMN: BLUE SIDE (Aliados) */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg shadow-lg flex flex-col overflow-hidden">
          <div className="bg-[#1e3a8a] py-2 px-4 flex justify-between items-center text-white">
            <h3 className="font-bold tracking-widest text-sm">EQUIPO AZUL</h3>
            <div className="text-xs font-bold">
              ⚔️ AD {compB.ad}% | 🔮 AP {compB.ap}% | 🛡️ {compB.tanks}
            </div>
          </div>
          
          <div className="grid grid-cols-12 gap-2 p-3 bg-[#0f172a] border-b border-[#1e293b] text-[#94a3b8] font-bold text-[10px] tracking-widest">
            <div className="col-span-4 text-left pl-14">CAMPEÓN</div>
            <div className="col-span-2 text-center">K / D / A</div>
            <div className="col-span-2 text-center">FARM</div>
            <div className="col-span-4 text-left">ITEMS</div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {state.blueTeam?.map(p => renderPlayer(p, true))}
          </div>
        </div>

        {/* RIGHT COLUMN: RED SIDE (Enemigos) */}
        <div className="bg-[#150a0a] border border-[#450a0a] rounded-lg shadow-lg flex flex-col overflow-hidden">
          <div className="bg-[#7f1d1d] py-2 px-4 flex justify-between items-center text-white">
            <h3 className="font-bold tracking-widest text-sm">EQUIPO ROJO</h3>
            <div className="text-xs font-bold">
              ⚔️ AD {compR.ad}% | 🔮 AP {compR.ap}% | 🛡️ {compR.tanks}
            </div>
          </div>

          <div className="grid grid-cols-12 gap-2 p-3 bg-[#2a0f0f] border-b border-[#450a0a] text-[#fca5a5] font-bold text-[10px] tracking-widest">
            <div className="col-span-4 text-left pl-14">CAMPEÓN</div>
            <div className="col-span-2 text-center">K / D / A</div>
            <div className="col-span-2 text-center">FARM</div>
            <div className="col-span-4 text-left">ITEMS</div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {state.redTeam?.map(p => renderPlayer(p, false))}
          </div>
        </div>

      </div>
    </div>
  );
};

export default InGameView;
