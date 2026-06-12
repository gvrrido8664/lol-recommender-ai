import React, { useState, useEffect } from 'react';
import { simularEnfrentamiento, apiClient } from '../api/client';

const ProgressBar = ({ label, valAliado, valEnemigo, maxVal }: any) => {
  const pctA = Math.min(100, (valAliado / maxVal) * 100);
  const pctE = Math.min(100, (valEnemigo / maxVal) * 100);
  const delta = valAliado - valEnemigo;
  
  return (
    <div className="flex items-center space-x-4 mb-2">
      <div className="w-24 text-[10px] text-[#94a3b8]">{label}</div>
      <div className="flex-1 bg-[#1e293b] rounded-sm h-6 flex justify-end">
        {valAliado > 0 && <div className="bg-[#10b981] h-full rounded-l-sm" style={{ width: `${pctA}%` }}></div>}
      </div>
      <div className="w-6 text-center text-xs font-bold text-[#e2e8f0]">{valAliado}</div>
      <div className="w-10 text-center text-[10px] font-bold">
        {delta > 0 ? <span className="text-[#10b981]">(+{delta})</span> : 
         delta < 0 ? <span className="text-[#ef4444]">({delta})</span> : 
         <span className="text-[#94a3b8]">(=)</span>}
      </div>
      <div className="w-6 text-center text-xs font-bold text-[#e2e8f0]">{valEnemigo}</div>
      <div className="flex-1 bg-[#1e293b] rounded-sm h-6">
        {valEnemigo > 0 && <div className="bg-[#ef4444] h-full rounded-r-sm" style={{ width: `${pctE}%` }}></div>}
      </div>
    </div>
  );
};

const MiniBar = ({ label, valAliado, valEnemigo, maxVal }: any) => {
  const delta = valAliado - valEnemigo;
  const isAdvantage = delta > 0;
  const isDisadvantage = delta < 0;
  
  const pct = Math.min(100, (Math.max(valAliado, valEnemigo) / maxVal) * 100);

  return (
    <div className="flex items-center space-x-3 mb-1.5 w-full">
      <div className="w-20 text-[10px] text-[#94a3b8] text-right">{label}</div>
      <div className="flex-1 bg-[#1e293b] rounded-full h-1.5 overflow-hidden flex">
        {isAdvantage && <div className="bg-[#10b981] h-full" style={{ width: `${pct}%` }}></div>}
        {isDisadvantage && <div className="bg-[#ef4444] h-full" style={{ width: `${pct}%` }}></div>}
        {delta === 0 && <div className="bg-[#64748b] h-full" style={{ width: `${pct}%` }}></div>}
      </div>
    </div>
  );
};

const SimuladorView: React.FC = () => {
  const [aliado, setAliado] = useState('Gangplank');
  const [enemigo, setEnemigo] = useState('Garen');
  const [rol, setRol] = useState('TOP');
  
  const [campeones, setCampeones] = useState<string[]>([]);
  const [champMap, setChampMap] = useState<Record<string, string>>({});
  const [resultado, setResultado] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Cargar lista y mapeo de IDs de imágenes
  useEffect(() => {
    apiClient.get('/campeones').then((res) => {
      if (res.data.status === 'success') {
        const nombresList: string[] = [];
        const mapa: Record<string, string> = {};
        
        Object.values(res.data.data).forEach((c: any) => {
           nombresList.push(c.nombre);
           mapa[c.nombre] = c.id;
        });
        
        mapa["Wukong"] = "MonkeyKing";
        mapa["MaestroYi"] = "MasterYi";
        mapa["KhaZix"] = "Khazix";
        
        setChampMap(mapa);
        setCampeones(Array.from(new Set(nombresList)).sort());
      }
    }).catch(console.error);
  }, []);

  const getChampImage = (name: string) => {
    const internalId = champMap[name] || name;
    const cleanId = internalId.replace(/\s+/g, '');
    return `https://ddragon.leagueoflegends.com/cdn/14.8.1/img/champion/${cleanId}.png`;
  };

  const handleSimular = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await simularEnfrentamiento(aliado, enemigo, rol);
      if (res.status === 'success') {
        setResultado(res.data);
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError('Error al conectar con la API.');
    }
    setLoading(false);
  };

  const assignIcon = (text: string) => {
    const lower = text.toLowerCase();
    if (lower.includes('ventaja')) return '🟢';
    if (lower.includes('inferior') || lower.includes('peligro') || lower.includes('cuidado')) return '🔴';
    if (lower.includes('supera') || lower.includes('escalado') || lower.includes('late')) return '📈';
    if (lower.includes('daño') || lower.includes('armadura') || lower.includes('defensiv')) return '🛡️';
    if (lower.includes('hyper-carry') || lower.includes('seguro')) return '🏃';
    return '🔸';
  };

  return (
    <div className="flex flex-col gap-6 h-full px-2 text-sm font-sans pb-6">
      
      {/* 1. CONFIGURACIÓN DEL MATCHUP */}
      <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-5 shadow-lg flex-shrink-0">
        <h3 className="text-[#ef4444] font-bold text-xs tracking-widest mb-4">CONFIGURACIÓN DEL MATCHUP</h3>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center space-x-2">
            <label className="text-[10px] text-[#94a3b8] font-bold">Línea:</label>
            <select 
              value={rol}
              onChange={(e) => setRol(e.target.value)}
              className="bg-[#05080f] border border-[#1e293b] text-[#e2e8f0] px-3 py-1.5 rounded-md focus:outline-none focus:border-[#ef4444] text-xs w-32"
            >
              <option value="TOP">TOP</option>
              <option value="JUNGLE">JUNGLA</option>
              <option value="MID">MID</option>
              <option value="BOTTOM">ADC</option>
              <option value="SUPPORT">SUPPORT</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-[10px] text-[#94a3b8] font-bold">Tu Pick:</label>
            <select 
              value={aliado}
              onChange={(e) => setAliado(e.target.value)}
              className="bg-[#05080f] border border-[#1e293b] text-[#e2e8f0] px-3 py-1.5 rounded-md focus:outline-none focus:border-[#10b981] text-xs w-48"
            >
              {campeones.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="text-[#ef4444] font-black text-sm mx-2">VS</div>

          <div className="flex items-center space-x-2 flex-1">
            <select 
              value={enemigo}
              onChange={(e) => setEnemigo(e.target.value)}
              className="bg-[#05080f] border border-[#1e293b] text-[#e2e8f0] px-3 py-1.5 rounded-md focus:outline-none focus:border-[#ef4444] text-xs w-48"
            >
              {campeones.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <button 
            onClick={handleSimular}
            disabled={loading}
            className="bg-[#ef4444] hover:bg-[#dc2626] text-white font-bold py-1.5 px-6 rounded-md transition-colors shadow-lg tracking-wider text-xs"
          >
            {loading ? 'SIMULANDO...' : 'SIMULAR ENFRENTAMIENTO'}
          </button>
        </div>
        {error && <div className="mt-2 text-[#ef4444] text-[10px] font-bold">{error}</div>}
      </div>

      {/* 2. RESULTADO PREDICTIVO (IA) */}
      <div className="bg-[#0b0f19] border border-[#450a0a] rounded-xl p-6 shadow-2xl flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar">
        <h3 className="text-[#ef4444] font-bold text-xs tracking-widest mb-6">RESULTADO PREDICTIVO (IA)</h3>
        
        {resultado ? (
          <div className="flex flex-col space-y-6">
            
            {/* Cabecera: Iconos y Winrate */}
            <div className="flex justify-center items-center space-x-12 px-8">
              
              <div className="flex flex-col items-center">
                <div className="w-24 h-24 rounded border border-[#10b981] p-1 bg-black mb-2 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                  <img src={getChampImage(aliado)} alt={aliado} className="w-full h-full object-cover" onError={(e) => e.currentTarget.src = 'https://ddragon.leagueoflegends.com/cdn/14.8.1/img/profileicon/29.png'} />
                </div>
                <span className="text-[#10b981] font-bold text-xs">{aliado}</span>
              </div>
              
              <div className="flex flex-col items-center min-w-[300px]">
                <h1 className="text-5xl font-black mb-1" style={{ color: resultado.nivel_color }}>
                  {resultado.probabilidad}%
                </h1>
                <p className="font-bold text-[10px] tracking-widest mb-1" style={{ color: resultado.nivel_color }}>
                  ⚔️ MATCHUP DE HABILIDAD (50/50)
                </p>
                <p className="text-[9px] text-[#64748b] mb-4">
                  (sin datos reales en BD)
                </p>
                
                {/* Mini barras resumen */}
                <div className="w-full bg-[#05080f] rounded-lg border border-[#1e293b] p-3">
                   <MiniBar label="CC (Control)" valAliado={resultado.stats?.cc?.aliado || 0} valEnemigo={resultado.stats?.cc?.enemigo || 0} maxVal={5} />
                   <MiniBar label="Movilidad" valAliado={resultado.stats?.movilidad?.aliado || 0} valEnemigo={resultado.stats?.movilidad?.enemigo || 0} maxVal={5} />
                   <MiniBar label="Early Game" valAliado={resultado.stats?.early?.aliado || 0} valEnemigo={resultado.stats?.early?.enemigo || 0} maxVal={3} />
                </div>
              </div>

              <div className="flex flex-col items-center">
                <div className="w-24 h-24 rounded border border-[#ef4444] p-1 bg-black mb-2 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                  <img src={getChampImage(enemigo)} alt={enemigo} className="w-full h-full object-cover" onError={(e) => e.currentTarget.src = 'https://ddragon.leagueoflegends.com/cdn/14.8.1/img/profileicon/29.png'} />
                </div>
                <span className="text-[#ef4444] font-bold text-xs">{enemigo}</span>
              </div>
            </div>

            <div className="border-t border-[#1e293b]"></div>

            {/* Stats Comparativas */}
            <div>
              <h4 className="text-[#e2e8f0] font-bold text-xs mb-2 flex items-center tracking-widest">
                <span className="text-[#f59e0b] mr-2">⚡</span> STATS COMPARATIVAS
              </h4>
              <p className="text-[9px] text-[#64748b] mb-4">
                {aliado} <span className="text-[#10b981]">verde</span> → DELTA ← <span className="text-[#ef4444]">rojo</span> {enemigo}
              </p>
              
              <div className="max-w-2xl">
                <ProgressBar label="Movilidad" valAliado={resultado.stats?.movilidad?.aliado || 0} valEnemigo={resultado.stats?.movilidad?.enemigo || 0} maxVal={5} />
                <ProgressBar label="Control (CC)" valAliado={resultado.stats?.cc?.aliado || 0} valEnemigo={resultado.stats?.cc?.enemigo || 0} maxVal={5} />
                <ProgressBar label="Early Game" valAliado={resultado.stats?.early?.aliado || 0} valEnemigo={resultado.stats?.early?.enemigo || 0} maxVal={3} />
                <ProgressBar label="Escalado" valAliado={resultado.stats?.escalado?.aliado || 0} valEnemigo={resultado.stats?.escalado?.enemigo || 0} maxVal={4} />
              </div>
              
              <p className="text-[10px] text-[#94a3b8] mt-4">
                Daño: <span className="text-[#10b981] font-bold">{aliado} {resultado.info_aliado?.dano || 'AD'}</span> vs <span className="text-[#ef4444] font-bold">{enemigo} {resultado.info_enemigo?.dano || 'AD'}</span> | 
                Clase: <span className="text-[#10b981] font-bold">{resultado.info_aliado?.clase || 'Fighter'}</span> vs <span className="text-[#ef4444] font-bold">{resultado.info_enemigo?.clase || 'Fighter'}</span>
              </p>
            </div>

            <div className="border-t border-[#1e293b]"></div>

            {/* Qué ve la IA */}
            <div>
              <h4 className="text-[#e2e8f0] font-bold text-xs mb-4 flex items-center tracking-widest">
                <span className="text-[#d946ef] mr-2">🧠</span> QUE VE LA IA
              </h4>
              <ul className="space-y-1.5 list-none">
                {resultado.insights?.length > 0 ? (
                  resultado.insights.map((ins: any, idx: number) => {
                    const icon = assignIcon(ins.texto);
                    return (
                      <li key={idx} className="text-[11px] text-[#94a3b8] flex items-start">
                        <span className="mr-2 opacity-80">{icon}</span>
                        <span>
                          {/* Resaltamos la ventaja o desventaja en el texto si la tiene */}
                          {ins.texto.includes('(+') || ins.texto.includes('(-') ? (
                            <span className={ins.texto.includes('(+') ? 'text-[#10b981]' : 'text-[#ef4444]'}>
                              {ins.texto.split(':')[0]}: 
                            </span>
                          ) : null}
                          <span className="ml-1">
                            {ins.texto.includes(':') ? ins.texto.substring(ins.texto.indexOf(':') + 1) : ins.texto}
                          </span>
                        </span>
                      </li>
                    );
                  })
                ) : (
                  <li className="text-xs text-[#64748b]">Análisis detallado no disponible para este matchup.</li>
                )}
              </ul>
            </div>

          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-[#475569]">
            <div className="text-5xl mb-3 opacity-20">🤖</div>
            <p className="text-xs">Selecciona los campeones y presiona Simular para ver el análisis de la IA.</p>
          </div>
        )}
      </div>

    </div>
  );
};

export default SimuladorView;
