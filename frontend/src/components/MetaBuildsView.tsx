import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';

interface BuildData {
  starters: number[];
  finales: number[];
  runas: string[];
  spells: string[];
}

interface MatchupData {
  id: string;
  name: string;
  wr: number;
  matches: number;
  build: BuildData;
}

const MetaBuildsView: React.FC = () => {
  const [linea, setLinea] = useState('MID');
  const [vsRival, setVsRival] = useState('Yasuo');
  const [selectedChamp, setSelectedChamp] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [matchups, setMatchups] = useState<MatchupData[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Selector states
  const [campeones, setCampeones] = useState<string[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiClient.get('/campeones').then((res) => {
      if (res.data.status === 'success') {
        const nombresList: string[] = [];
        Object.values(res.data.data).forEach((c: any) => nombresList.push(c.nombre));
        setCampeones(Array.from(new Set(nombresList)).sort());
      }
    }).catch(console.error);

    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchMetaBuilds = async () => {
    if (!vsRival.trim()) return;
    setLoading(true);
    setError(null);
    setSelectedChamp(null);
    try {
      const res = await fetch(`http://localhost:8000/api/meta-builds?linea=${linea}&vs=${vsRival}`);
      const data = await res.json();
      if (data.status === 'success') {
        if (data.data.length === 0) {
          setError("No se encontraron suficientes datos (mínimo 20 partidas). Prueba con otro campeón.");
          setMatchups([]);
        } else {
          setMatchups(data.data);
          if (data.data.length > 0) {
            setSelectedChamp(data.data[0].id); // Seleccionar el primero por defecto
          }
        }
      } else {
        setError(data.message || "Error al obtener datos");
      }
    } catch (err) {
      console.error(err);
      setError("Error de red al conectar con el backend.");
    } finally {
      setLoading(false);
    }
  };

  const selectedData = matchups.find(m => m.id === selectedChamp);

  return (
    <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2 pb-6">
      
      {/* 1. TOP BAR: FILTERS */}
      <div className="flex items-center space-x-4 mb-6 bg-[#0f1423] p-4 rounded-xl border border-[#1e293b] shadow-md">
        <div className="flex items-center space-x-3">
          <label className="text-[#94a3b8] font-bold text-xs uppercase tracking-widest">Línea</label>
          <select 
            value={linea}
            onChange={(e) => setLinea(e.target.value)}
            className="bg-[#0b0f19] border border-[#1e293b] text-[#e2e8f0] px-4 py-2 rounded-lg focus:outline-none focus:border-[#38bdf8] font-bold"
          >
            <option value="TOP">TOP</option>
            <option value="JUNGLA">JUNGLA</option>
            <option value="MID">MID</option>
            <option value="ADC">ADC</option>
            <option value="SUPPORT">SUPPORT</option>
          </select>
        </div>

        <div className="flex items-center space-x-3" ref={dropdownRef}>
          <label className="text-[#94a3b8] font-bold text-xs uppercase tracking-widest">Vs Enemigo</label>
          <div className="relative">
            <div 
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="bg-[#0b0f19] border border-[#1e293b] text-[#e2e8f0] px-4 py-2 rounded-lg cursor-pointer flex justify-between items-center w-48 font-bold"
            >
              <span>{vsRival}</span>
              <span className="text-[#64748b] ml-2">▼</span>
            </div>
            
            {dropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-full bg-[#0f1423] border border-[#1e293b] rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-60">
                <input 
                  type="text"
                  placeholder="Buscar..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-[#0b0f19] border-b border-[#1e293b] text-[#e2e8f0] px-3 py-2 text-xs focus:outline-none focus:border-[#ef4444]"
                  autoFocus
                />
                <div className="overflow-y-auto flex-1 custom-scrollbar">
                  {campeones.filter(c => c.toLowerCase().includes(search.toLowerCase())).map(c => (
                    <div 
                      key={c}
                      className="px-3 py-2 text-xs text-[#e2e8f0] hover:bg-[#1e293b] cursor-pointer"
                      onClick={() => {
                        setVsRival(c);
                        setSearch('');
                        setDropdownOpen(false);
                      }}
                    >
                      {c}
                    </div>
                  ))}
                  {campeones.filter(c => c.toLowerCase().includes(search.toLowerCase())).length === 0 && (
                    <div className="px-3 py-2 text-xs text-[#64748b]">No encontrado</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <button 
          onClick={fetchMetaBuilds}
          disabled={loading}
          className="bg-[#ef4444] hover:bg-[#dc2626] text-white font-bold py-2 px-8 rounded-lg shadow-lg transition duration-200 tracking-widest text-xs uppercase disabled:opacity-50"
        >
          {loading ? 'Analizando...' : 'Analizar Counters'}
        </button>

        {error && <span className="text-[#ef4444] font-bold ml-4">{error}</span>}
      </div>

      {/* 2. MAIN GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        
        {/* LEFT COLUMN: MATCHUPS TABLE */}
        <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl flex flex-col overflow-hidden shadow-lg">
          <div className="grid grid-cols-12 gap-2 p-4 border-b border-[#1e293b] text-[#ef4444] font-bold text-[10px] tracking-widest bg-[#131b2f]">
            <div className="col-span-6 pl-4">MEJORES RESPUESTAS (ALIADO)</div>
            <div className="col-span-3 text-center">WINRATE %</div>
            <div className="col-span-3 text-center">PARTIDAS</div>
          </div>
          
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {loading ? (
              <div className="flex items-center justify-center h-full text-[#94a3b8] italic">Calculando estadísticas masivas...</div>
            ) : matchups.length === 0 ? (
              <div className="flex items-center justify-center h-full text-[#94a3b8] italic">Selecciona un campeón y presiona Analizar</div>
            ) : (
              <table className="w-full text-left text-xs">
                <tbody>
                  {matchups.map((champ) => (
                    <tr 
                      key={champ.id} 
                      onClick={() => setSelectedChamp(champ.id)}
                      className={`border-b border-[#1e293b] cursor-pointer transition ${
                        selectedChamp === champ.id ? 'bg-[#1e293b] border-l-4 border-l-[#ef4444]' : 'hover:bg-[#151d2e] border-l-4 border-l-transparent'
                      }`}
                    >
                      <td className="py-3 px-4 flex items-center space-x-3">
                        <img 
                          src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${champ.id}.png`} 
                          className="w-10 h-10 rounded border border-[#334155] shadow-md"
                          onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
                          alt={champ.name}
                        />
                        <span className="text-[#e2e8f0] font-bold text-sm">{champ.name}</span>
                      </td>
                      <td className={`py-3 text-center font-black text-sm ${champ.wr >= 55 ? 'text-[#10b981]' : champ.wr >= 52 ? 'text-[#38bdf8]' : 'text-[#e2e8f0]'}`}>
                        {champ.wr.toFixed(1)}%
                      </td>
                      <td className="py-3 text-center text-[#94a3b8] font-bold">
                        {champ.matches}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: SETUP & BUILD OPTIMAS */}
        <div className="flex flex-col space-y-4">
          <h3 className="text-[#ef4444] font-bold text-xs tracking-widest pl-2 uppercase">
            {selectedData ? `SETUP & BUILD ÓPTIMAS PARA ${selectedData.name}` : 'SETUP & BUILD ÓPTIMAS'}
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 flex-1">
            
            {/* Runas Recomendadas */}
            <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-3 shadow-lg flex flex-col items-center">
              <h4 className="text-[#38bdf8] font-bold text-[10px] tracking-widest mb-3">RUNAS PRINCIPALES</h4>
              
              {selectedData ? (
                <div className="flex flex-col items-center space-y-2 w-full">
                  {/* Primary Tree */}
                  {selectedData.build.runas[0] && (
                    <div className="w-8 h-8 bg-[#0f1423] rounded-full border border-[#38bdf8] p-0.5 mb-1">
                      <img src={selectedData.build.runas[0]} alt="Primary Style" className="w-full h-full object-contain" />
                    </div>
                  )}
                  <div className="flex flex-col space-y-1.5">
                    {selectedData.build.runas.slice(1, 5).map((url, idx) => url ? (
                      <div key={idx} className={`w-8 h-8 bg-[#0f1423] rounded-full border ${idx === 0 ? 'border-[#38bdf8] w-10 h-10' : 'border-[#334155]'} p-0.5`}>
                        <img src={url} alt={`Rune ${idx}`} className="w-full h-full object-contain" />
                      </div>
                    ) : null)}
                  </div>
                  
                  {/* Secondary Tree */}
                  <div className="w-full border-t border-[#1e293b] my-2"></div>
                  <h4 className="text-[#10b981] font-bold text-[10px] tracking-widest mb-2">RUNAS SECUNDARIAS</h4>

                  {selectedData.build.runas[5] && (
                    <div className="w-6 h-6 opacity-80 mb-1">
                       <img src={selectedData.build.runas[5]} alt="Secondary Style" className="w-full h-full object-contain grayscale opacity-70" />
                    </div>
                  )}
                  <div className="flex space-x-2">
                    {selectedData.build.runas.slice(6, 8).map((url, idx) => url ? (
                      <div key={idx} className="w-7 h-7 bg-[#0f1423] rounded-full border border-[#334155] p-0.5">
                        <img src={url} alt={`Subrune ${idx}`} className="w-full h-full object-contain" />
                      </div>
                    ) : null)}
                  </div>
                  
                  {/* Shards */}
                  <div className="flex justify-center space-x-1.5 mt-2 w-full">
                    {selectedData.build.runas.slice(8, 11).map((url, idx) => url ? (
                      <img key={idx} src={url} className="w-5 h-5 rounded-full border border-[#1e293b]" alt={`Shard ${idx}`} />
                    ) : null)}
                  </div>
                </div>
              ) : (
                 <span className="text-[#475569] italic text-xs">Selecciona un campeón</span>
              )}
            </div>

            {/* Hechizos */}
            <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-3 shadow-lg flex flex-col items-center">
              <h4 className="text-yellow-500 font-bold text-[10px] tracking-widest mb-6">HECHIZOS</h4>
              <div className="flex flex-col space-y-4 items-center flex-1 justify-center">
                {selectedData ? (
                  selectedData.build.spells.map((url, idx) => url ? (
                    <img 
                      key={idx}
                      src={url} 
                      alt={`Spell ${idx}`}
                      className="w-12 h-12 rounded-lg shadow-lg border border-[#334155]"
                    />
                  ) : null)
                ) : (
                  <span className="text-[#475569] italic text-xs">--</span>
                )}
              </div>
            </div>

            {/* Build Óptima */}
            <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl p-3 shadow-lg flex flex-col items-center">
              <h4 className="text-[#ef4444] font-bold text-[10px] tracking-widest mb-4">INICIO (EARLY)</h4>
              
              <div className="flex justify-center space-x-2 mb-4 flex-wrap">
                {selectedData ? (
                  selectedData.build.starters.map((id, idx) => (
                    <img key={`start-${idx}`} src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/item/${id}.png`} className="w-8 h-8 rounded-lg border border-[#334155] shadow-md mb-2" alt={`Item ${id}`} />
                  ))
                ) : (
                  <span className="text-[#475569] italic text-xs">--</span>
                )}
              </div>

              <div className="w-full border-t border-[#1e293b] my-2"></div>

              <h4 className="text-[#a855f7] font-bold text-[10px] tracking-widest mb-3">CORE BUILD (MID/LATE)</h4>
              
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                {selectedData ? (
                  selectedData.build.finales.map((id, idx) => (
                    <img 
                      key={`core-${idx}`} 
                      src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/item/${id}.png`} 
                      className="w-10 h-10 rounded-lg border border-[#a855f7] shadow-[0_0_10px_rgba(168,85,247,0.3)] transition hover:scale-110" 
                      alt={`Item ${id}`} 
                    />
                  ))
                ) : (
                  <span className="text-[#475569] italic text-xs">--</span>
                )}
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
};

export default MetaBuildsView;
