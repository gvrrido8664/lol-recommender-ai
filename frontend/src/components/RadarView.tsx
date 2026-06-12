import React, { useState, useEffect } from 'react';

interface RadarState {
  isActive: boolean;
  myRole: string;
  allyPicks: string[];
  enemyPicks: string[];
  suggestions: Record<string, any[]>;
}

const RadarView: React.FC = () => {
  const [radar, setRadar] = useState<RadarState>({
    isActive: false,
    myRole: 'MID',
    allyPicks: [],
    enemyPicks: [],
    suggestions: {}
  });

  const [wsError, setWsError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: any;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws/radar');
      
      ws.onopen = () => {
        setWsError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setRadar(prev => ({ ...prev, ...data }));
        } catch (e) {
          console.error("Error parsing radar msg", e);
        }
      };

      ws.onerror = (e) => {
        setWsError('Desconectado del servidor local. Intentando reconectar...');
      };

      ws.onclose = () => {
        setRadar(prev => ({ ...prev, isActive: false }));
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  const renderChampList = (champs: string[], isEnemy: boolean) => {
    // Rellenamos hasta 5 huecos
    const slots = [...champs, ...Array(5 - champs.length).fill(null)].slice(0, 5);
    return (
      <div className="flex flex-col space-y-3 flex-1">
        {slots.map((c, i) => (
          <div key={i} className={`h-12 border border-[#1e293b] rounded-lg bg-[#0f1423] flex items-center px-3 ${isEnemy ? 'flex-row-reverse' : 'flex-row'}`}>
            {c ? (
              <>
                <img 
                  src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${c}.png`}
                  className="w-8 h-8 rounded-full border border-[#334155]"
                  alt={c}
                  onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
                />
                <span className={`font-bold text-[#e2e8f0] ${isEnemy ? 'mr-3' : 'ml-3'}`}>{c}</span>
              </>
            ) : (
              <span className="text-[#334155] italic mx-auto text-xs">Esperando...</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderStars = (pts: number) => {
    if (pts >= 9.0) return "⭐⭐⭐⭐⭐";
    if (pts >= 7.0) return "⭐⭐⭐⭐";
    if (pts >= 5.0) return "⭐⭐⭐";
    if (pts >= 3.0) return "⭐⭐";
    return "⭐";
  };

  return (
    <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2">
      
      {/* 1. TOP HEADER: STATUS */}
      <div className="flex justify-between items-center mb-4 px-2">
        <div className={`font-bold tracking-wide text-lg ${radar.isActive ? 'text-[#10b981] animate-pulse' : 'text-yellow-500 animate-pulse'}`}>
          {radar.isActive ? '⚡ DRAFT DETECTADO: ANALIZANDO' : 'Buscando Cliente de LoL (Entra a una partida)...'}
        </div>
        <div className="flex items-center space-x-2">
          {wsError && <span className="text-xs text-[#ef4444] font-bold mr-4">{wsError}</span>}
          <span className="text-[#64748b] italic">Rol Asignado:</span>
          <span className={`text-xl font-black ${radar.isActive ? 'text-[#38bdf8]' : 'text-[#64748b]'}`}>
            {radar.isActive ? radar.myRole : '--'}
          </span>
        </div>
      </div>

      {/* 2. TIP BAR */}
      <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-3 mb-6 flex items-center shadow-md">
        <span className="mr-2">💡</span>
        <span className="text-[#38bdf8] font-bold mr-1">Consejo en Vivo:</span>
        <span className="text-[#94a3b8]">Las recomendaciones se actualizan automáticamente cada vez que un campeón es seleccionado en tu equipo o en el rival.</span>
      </div>

      {/* 3. MAIN GRID: 3 COLUMNS */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
        
        {/* LEFT COLUMN: ENEMIGOS */}
        <div className="col-span-1 flex flex-col space-y-4">
          <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-5 shadow-lg flex-1 flex flex-col">
            <h3 className="text-[#ef4444] font-bold tracking-widest mb-4 text-center">EQUIPO ENEMIGO</h3>
            
            {renderChampList(radar.enemyPicks, true)}
            
          </div>
        </div>

        {/* CENTER COLUMN: RECOMENDACIONES */}
        <div className="col-span-2 flex flex-col space-y-4 overflow-y-auto custom-scrollbar">
          {!radar.isActive ? (
             <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-[#334155] rounded-xl bg-[#0f1423] bg-opacity-50">
               <div className="w-16 h-16 border-4 border-[#38bdf8] border-t-transparent rounded-full animate-spin mb-4"></div>
               <p className="text-[#94a3b8] font-bold tracking-widest">ESPERANDO FASE DE SELECCIÓN</p>
             </div>
          ) : (
            <div className="flex flex-col space-y-4 flex-1">
              {Object.keys(radar.suggestions).length === 0 ? (
                 <div className="flex-1 flex items-center justify-center text-[#94a3b8] italic">Analizando mejores opciones...</div>
              ) : (
                Object.entries(radar.suggestions).map(([categoria, lista]) => (
                  <div key={categoria} className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-4 shadow-lg">
                    <h3 className="text-[#38bdf8] font-bold text-xs tracking-widest mb-3 uppercase border-b border-[#1e293b] pb-2">
                      {categoria}
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      {lista.slice(0, 4).map((item, idx) => {
                        const champName = item[0];
                        const pts = item[1];
                        const reason = item[2];
                        const ptsColor = pts >= 8.0 ? 'text-[#10b981]' : pts >= 5.0 ? 'text-yellow-500' : 'text-[#ef4444]';
                        
                        return (
                          <div key={idx} className="bg-[#0f1423] p-2 rounded-lg border border-[#1e293b] flex items-start space-x-3">
                            <img 
                              src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${champName}.png`}
                              className="w-10 h-10 rounded shadow-sm"
                              alt={champName}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-center mb-1">
                                <span className="font-bold text-[#e2e8f0] text-sm truncate">{champName}</span>
                                <span className={`font-black text-xs ${ptsColor}`}>{pts.toFixed(1)}</span>
                              </div>
                              <div className="text-[10px] text-yellow-500 mb-1">{renderStars(pts)}</div>
                              <p className="text-[10px] text-[#64748b] leading-tight line-clamp-2" title={reason}>
                                {reason}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: ALIADOS */}
        <div className="col-span-1 flex flex-col space-y-4">
          <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-5 shadow-lg flex-1 flex flex-col">
            <h3 className="text-[#38bdf8] font-bold tracking-widest mb-4 text-center">TU EQUIPO</h3>
            
            {renderChampList(radar.allyPicks, false)}
            
          </div>
        </div>

      </div>
    </div>
  );
};

export default RadarView;
