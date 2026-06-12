import React, { useState } from 'react';

interface BanData {
  id: string;
  name: string;
  banrate: number;
  matches: number;
}

const TierListBansView: React.FC = () => {
  const [linea, setLinea] = useState('TOP');
  const [tipoFiltro, setTipoFiltro] = useState('global');
  const [hoveredChamp, setHoveredChamp] = useState<string | null>(null);
  
  const [banList, setBanList] = useState<BanData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBans = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/bans?linea=${linea}&tipo=${tipoFiltro}`);
      const data = await res.json();
      if (data.status === 'success') {
        if (data.data.length === 0) {
          setError("No se encontraron bans sugeridos para esta línea.");
          setBanList([]);
        } else {
          setBanList(data.data);
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

  return (
    <div className="flex flex-col h-full bg-[#05080f] text-sm font-sans px-2 pb-6">
      
      {/* 1. TOP BAR: FILTERS */}
      <div className="flex items-center space-x-6 mb-6 bg-[#0f1423] p-4 rounded-xl border border-[#1e293b] shadow-md">
        
        <div className="flex items-center space-x-3">
          <label className="text-[#94a3b8] font-bold text-xs uppercase tracking-widest">Selecciona la Línea a Proteger:</label>
          <select 
            value={linea}
            onChange={(e) => setLinea(e.target.value)}
            className="bg-[#0b0f19] border border-[#1e293b] text-[#e2e8f0] px-4 py-2 rounded-lg focus:outline-none focus:border-[#38bdf8] font-bold w-32"
          >
            <option value="TOP">TOP</option>
            <option value="JUNGLE">JUNGLA</option>
            <option value="MID">MID</option>
            <option value="ADC">ADC</option>
            <option value="SUPPORT">SUPPORT</option>
          </select>
        </div>

        <div className="flex items-center space-x-6 bg-[#0b0f19] px-4 py-2 rounded-lg border border-[#1e293b]">
          <label className="flex items-center space-x-2 cursor-pointer">
            <input 
              type="radio" 
              name="filtro" 
              value="global" 
              checked={tipoFiltro === 'global'} 
              onChange={() => setTipoFiltro('global')}
              className="accent-[#38bdf8] w-4 h-4"
            />
            <span className="text-[#e2e8f0] font-bold text-xs uppercase tracking-widest">Global</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer">
            <input 
              type="radio" 
              name="filtro" 
              value="personal" 
              checked={tipoFiltro === 'personal'} 
              onChange={() => setTipoFiltro('personal')}
              className="accent-[#38bdf8] w-4 h-4"
            />
            <span className="text-[#e2e8f0] font-bold text-xs uppercase tracking-widest">Personal (LCU)</span>
          </label>
        </div>

        <button 
          onClick={fetchBans}
          disabled={loading}
          className="bg-[#0f172a] hover:bg-[#1e293b] border border-[#1e293b] hover:border-[#38bdf8] text-[#e2e8f0] font-bold py-2 px-6 rounded-lg transition duration-200 text-xs tracking-widest disabled:opacity-50"
        >
          {loading ? 'ANALIZANDO...' : 'ANALIZAR BANS DEL META'}
        </button>

        {error && <span className="text-[#ef4444] font-bold text-xs">{error}</span>}
      </div>

      {/* 2. MAIN TABLE */}
      <div className="bg-[#0b0f19] border border-[#1e293b] rounded-xl flex flex-col flex-1 shadow-2xl overflow-hidden min-h-0">
        
        {/* Table Container */}
        <div className="flex-1 overflow-y-auto custom-scrollbar relative">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-[#94a3b8] italic">
              <div className="w-12 h-12 border-4 border-[#38bdf8] border-t-transparent rounded-full animate-spin mb-4"></div>
              <span>Analizando datos de {tipoFiltro === 'global' ? 'miles de partidas...' : 'tus partidas recientes...'}</span>
            </div>
          ) : banList.length === 0 ? (
            <div className="flex items-center justify-center h-full text-[#94a3b8] italic">
              {error ? "" : "Selecciona una línea y presiona Analizar Bans"}
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              
              <thead className="sticky top-0 bg-[#0b0f19] z-10">
                <tr>
                  <th className="py-4 px-8 text-[#64748b] font-bold tracking-widest border-b-2 border-[#ef4444] text-center w-1/3">
                    CAMPEÓN
                  </th>
                  <th className="py-4 px-8 text-[#64748b] font-bold tracking-widest border-b-2 border-[#ef4444] text-center w-1/3">
                    {tipoFiltro === 'global' ? 'BANRATE SUGERIDO %' : 'FRECUENCIA DE APARICIÓN %'}
                  </th>
                  <th className="py-4 px-8 text-[#64748b] font-bold tracking-widest border-b-2 border-[#ef4444] text-center w-1/3">
                    PARTIDAS ANALIZADAS
                  </th>
                </tr>
              </thead>
              
              <tbody>
                {banList.map((champ) => (
                  <tr 
                    key={champ.id} 
                    onMouseEnter={() => setHoveredChamp(champ.name)}
                    onMouseLeave={() => setHoveredChamp(null)}
                    className={`border-b border-[#1e293b] transition duration-150 ${
                      hoveredChamp === champ.name ? 'bg-[#1e3a8a]/40' : 'hover:bg-[#151d2e]'
                    }`}
                  >
                    {/* Campeón */}
                    <td className="py-3 px-8 flex items-center justify-center space-x-4">
                      <div className="flex items-center space-x-4 w-32">
                        <img 
                          src={`https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${champ.id}.png`} 
                          className="w-10 h-10 rounded-lg border border-[#334155] shadow-md"
                          onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
                          alt={champ.name}
                        />
                        <span className="text-[#e2e8f0] font-bold text-sm">{champ.name}</span>
                      </div>
                    </td>
                    
                    {/* Banrate */}
                    <td className="py-3 px-8 text-center text-[#ef4444] font-black text-sm">
                      {champ.banrate.toFixed(1)}%
                    </td>
                    
                    {/* Partidas */}
                    <td className="py-3 px-8 text-center text-[#94a3b8] font-bold">
                      {champ.matches}
                    </td>
                  </tr>
                ))}
              </tbody>
              
            </table>
          )}
        </div>
      </div>

    </div>
  );
};

export default TierListBansView;
