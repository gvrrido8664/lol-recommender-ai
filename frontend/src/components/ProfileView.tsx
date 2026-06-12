import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export default function ProfileView() {
  const [data, setData] = useState<any>(null);
  const [champions, setChampions] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [profileRes, champsRes] = await Promise.all([
          apiClient.get('/perfil'),
          apiClient.get('/campeones').catch(() => ({ data: { data: {} } })) // Fallback in case of error
        ]);
        
        if (profileRes.data.status === 'success') {
          setData(profileRes.data.data);
          setChampions(champsRes.data?.data || {});
        } else {
          setError(profileRes.data.message || 'Error desconocido');
        }
      } catch (err: any) {
        setError(err.message || 'Error de red');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="w-12 h-12 border-4 border-accentRed border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error || !data) {
    return <div className="flex h-full items-center justify-center text-accentRed font-bold">{error}</div>;
  }

  const { identidad, historial, coaching_report, fatiga } = data;

  // Helpers
  const getChampName = (id: string | number) => {
    const strId = String(id);
    // El backend nos manda algo como: { "266": { "nombre": "Aatrox", "key": "266", ... } }
    if (champions[strId]) {
      return champions[strId].nombre || champions[strId].name;
    }
    // Fallback por si acaso iteramos
    for (const key in champions) {
      if (String(champions[key].key) === strId) return champions[key].nombre || champions[key].name;
    }
    return `Champ ${id}`;
  };

  const getChampStars = (kda: number, wr: number) => {
    if (kda > 4 && wr >= 60) return '⭐⭐⭐';
    if (kda > 3 || wr >= 55) return '⭐⭐';
    if (kda > 2 || wr >= 50) return '⭐';
    return '';
  };

  // Aggregations for "Estadísticas de la temporada"
  const champStats: Record<string, { games: number, wins: number, kills: number, deaths: number, assists: number }> = {};
  
  historial.forEach((g: any) => {
    const p = g.participants[0];
    const cid = p.championId;
    if (!champStats[cid]) {
      champStats[cid] = { games: 0, wins: 0, kills: 0, deaths: 0, assists: 0 };
    }
    champStats[cid].games += 1;
    if (p.stats.win) champStats[cid].wins += 1;
    champStats[cid].kills += p.stats.kills;
    champStats[cid].deaths += p.stats.deaths;
    champStats[cid].assists += p.stats.assists;
  });

  const topChamps = Object.keys(champStats).map(cid => {
    const st = champStats[cid];
    const wr = (st.wins / st.games) * 100;
    const kda = st.deaths === 0 ? (st.kills + st.assists) : (st.kills + st.assists) / st.deaths;
    return { id: cid, name: getChampName(cid), games: st.games, wr, kda };
  }).sort((a, b) => b.games - a.games); // Sort by games played

  const bestChamp = topChamps.length > 0 ? topChamps.reduce((prev, current) => (prev.wr > current.wr) ? prev : current) : null;
  const mostPlayedChamp = topChamps.length > 0 ? topChamps[0] : null;

  // Fake Winrate por linea since mock doesn't have it (or parse it if it did)
  const lineStats = [
    { name: 'TOP', wr: 33 },
    { name: 'JUNGLA', wr: 80 },
    { name: 'MID', wr: 29 },
    { name: 'ADC', wr: 61 },
    { name: 'SUPPORT', wr: 70 },
  ];

  const getColorByWr = (wr: number) => wr >= 50 ? 'text-[#10b981]' : 'text-[#ef4444]';

  return (
    <div className="flex flex-col space-y-4 text-sm font-sans px-2">
      
      {/* 1. TOP SECTION: GRID */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* IDENTIDAD */}
        <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-5 flex justify-between items-start shadow-md">
          <div className="flex items-center space-x-4">
            <img 
              src={`https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/${identidad.icono}.jpg`} 
              className="w-16 h-16 rounded border border-[#334155]" 
              alt="Icon"
              onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
            />
            <div>
              <h2 className="text-xl font-bold text-white flex items-center">
                {identidad.nombre}
              </h2>
              <p className="text-[#64748b] text-xs mt-1">Nivel: {identidad.nivel}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[#10b981] font-bold text-sm flex items-center justify-end">
              <span className="w-3 h-3 bg-[#10b981] rounded-sm mr-1"></span>
              {identidad.soloq.tier} {identidad.soloq.division}
            </div>
            <p className="text-[#64748b] text-xs">{identidad.soloq.lp} PL | {identidad.soloq.wins}W {identidad.soloq.losses}L</p>
          </div>
        </div>

        {/* KPIs */}
        <div className="md:col-span-2 grid grid-cols-4 gap-4">
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-4 flex flex-col justify-center items-center shadow-md">
            <span className="text-xs text-[#64748b] font-bold mb-1">📊 WINRATE</span>
            <span className={`text-2xl font-black ${getColorByWr(coaching_report.metricas.wr)}`}>
              {coaching_report.metricas.wr.toFixed(0)}%
            </span>
          </div>
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-4 flex flex-col justify-center items-center shadow-md">
            <span className="text-xs text-[#64748b] font-bold mb-1">⚔️ KDA</span>
            <span className="text-2xl font-black text-[#38bdf8]">
              {coaching_report.metricas.kda.toFixed(2)}
            </span>
          </div>
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-4 flex flex-col justify-center items-center shadow-md">
            <span className="text-xs text-[#64748b] font-bold mb-1">🔥 MÁS JUGADO</span>
            <span className="text-xl font-bold text-[#e2e8f0]">
              {mostPlayedChamp ? mostPlayedChamp.name : 'N/A'}
            </span>
          </div>
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-4 flex flex-col justify-center items-center shadow-md">
            <span className="text-xs text-[#64748b] font-bold mb-1">🏆 MEJOR WR</span>
            <span className="text-xl font-bold text-[#10b981]">
              {bestChamp ? bestChamp.name : 'N/A'}
            </span>
          </div>
        </div>
      </div>



      {/* 3. BOTTOM SECTION: 2 COLUMNS */}
      <div className="flex flex-col lg:flex-row gap-4 h-full min-h-0">
        
        {/* LEFT COLUMN: ESTADISTICAS Y ESTADO */}
        <div className="w-full lg:w-1/3 flex flex-col space-y-4">

          {/* WINRATE LÍNEAS & FILTERS */}
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-4 flex flex-col shadow-md">
            <h3 className="text-xs font-bold text-[#ef4444] mb-3 tracking-widest">WINRATE POR LÍNEA</h3>
            <div className="flex justify-around w-full mb-6 border-b border-[#1e293b] pb-4">
              {lineStats.map((l, i) => (
                <div key={i} className="flex flex-col items-center">
                  <span className="text-xs text-[#94a3b8] font-bold mb-1">{l.name}</span>
                  <span className={`text-sm font-bold ${getColorByWr(l.wr)}`}>{l.wr}%</span>
                </div>
              ))}
            </div>
            
            <div className="flex flex-wrap gap-2">
              <button className="bg-transparent border border-[#334155] text-[#cbd5e1] px-3 py-1.5 rounded text-xs hover:bg-[#1e293b] transition flex-1">
                Todos
              </button>
              <button className="bg-transparent border border-[#334155] text-[#cbd5e1] px-3 py-1.5 rounded text-xs hover:bg-[#1e293b] transition flex-1">
                Modos
              </button>
              <button className="bg-transparent border border-[#ef4444] text-[#cbd5e1] px-3 py-1.5 rounded text-xs flex-1">
                Temp.
              </button>
            </div>
          </div>
          
          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg shadow-md flex-1 overflow-hidden flex flex-col">
            <div className="p-3 bg-[#131b2f] border-b border-[#1e293b]">
              <h3 className="text-xs font-bold text-[#94a3b8] tracking-widest flex items-center">
                <span className="w-2 h-4 bg-[#38bdf8] mr-2"></span> ESTADÍSTICAS DE LA TEMPORADA
              </h3>
            </div>
            <div className="overflow-y-auto custom-scrollbar flex-1 p-2">
              <table className="w-full text-left text-xs">
                <thead className="text-[#64748b] border-b border-[#1e293b]">
                  <tr>
                    <th className="py-2 font-medium">CAMPEÓN</th>
                    <th className="py-2 font-medium text-center">PARTIDAS</th>
                    <th className="py-2 font-medium text-center">WR</th>
                    <th className="py-2 font-medium text-center">KDA</th>
                  </tr>
                </thead>
                <tbody>
                  {topChamps.map((c, i) => (
                    <tr key={i} className="border-b border-[#1e293b] hover:bg-[#1e293b] transition">
                      <td className="py-2 flex items-center space-x-2">
                        <img 
                          src={`https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/${c.id}.png`} 
                          className="w-6 h-6 rounded-sm border border-[#334155]"
                          onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
                          alt=""
                        />
                        <span className="text-[#e2e8f0] font-medium">{c.name} <span className="text-yellow-500 text-[10px] ml-1">{getChampStars(c.kda, c.wr)}</span></span>
                      </td>
                      <td className="py-2 text-center text-[#cbd5e1]">{c.games}</td>
                      <td className={`py-2 text-center font-bold ${getColorByWr(c.wr)}`}>{c.wr.toFixed(1)}%</td>
                      <td className="py-2 text-center text-[#94a3b8]">{c.kda.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-[#0f1423] border border-[#1e293b] rounded-lg p-5 shadow-md flex-shrink-0">
            <h3 className="text-xs font-bold text-[#ef4444] mb-4 flex items-center tracking-widest">
              <span className="w-2 h-4 bg-[#ef4444] mr-2"></span> ESTADO MENTAL
            </h3>
            <div className="flex items-center space-x-3 mb-4">
              <span className="text-3xl">🔥</span>
              <span className="text-xl font-black text-[#10b981]">ÓPTIMO</span>
            </div>
            <div className="w-full h-1.5 bg-[#1e293b] rounded-full overflow-hidden mb-3">
              <div className="h-full bg-[#10b981] w-3/4"></div>
            </div>
            <p className="text-[11px] text-[#94a3b8] leading-tight">
              💡 La mente está fresca y los reflejos listos. Calienta con un normal o salta directo a ranked. Hoy es tu día.
            </p>
          </div>
        </div>

        {/* RIGHT COLUMN: HISTORIAL TABULAR */}
        <div className="w-full lg:w-2/3 bg-[#0f1423] border border-[#1e293b] rounded-lg shadow-md flex flex-col overflow-hidden">
          <div className="p-3 bg-[#131b2f] border-b border-[#1e293b]">
            <h3 className="text-xs font-bold text-[#ef4444] tracking-widest">HISTORIAL DE PARTIDAS</h3>
          </div>
          
          <div className="overflow-y-auto custom-scrollbar flex-1 p-2">
            <table className="w-full text-left text-xs">
              <thead className="text-[#64748b] border-b border-[#1e293b] sticky top-0 bg-[#0f1423] z-10">
                <tr>
                  <th className="py-3 px-2 font-medium">CAMPEÓN</th>
                  <th className="py-3 px-2 font-medium">RESULTADO</th>
                  <th className="py-3 px-2 font-medium">K/D/A</th>
                  <th className="py-3 px-2 font-medium">CS</th>
                  <th className="py-3 px-2 font-medium">DUR.</th>
                  <th className="py-3 px-2 font-medium">MODO</th>
                  <th className="py-3 px-2 font-medium">FECHA</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((g: any, i: number) => {
                  const p = g.participants[0];
                  const st = p.stats;
                  const win = st.win;
                  
                  const champName = getChampName(p.championId);
                  const kda = st.deaths === 0 ? (st.kills + st.assists) : (st.kills + st.assists) / st.deaths;
                  const stars = getChampStars(kda, win ? 100 : 0);
                  
                  const cs = st.totalMinionsKilled + st.neutralMinionsKilled;
                  const mins = Math.floor(g.gameDuration / 60);
                  const secs = g.gameDuration % 60;
                  const csMin = (cs / (g.gameDuration / 60)).toFixed(1);
                  
                  // Formatear Fecha (Mock: usamos creation)
                  const d = new Date(g.gameCreation);
                  const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;

                  return (
                    <tr key={i} className="border-b border-[#1e293b] hover:bg-[#1e293b] transition group relative">
                      {/* Borde izquierdo dinámico */}
                      <td className="py-2 px-2 flex items-center space-x-3 relative">
                        <div className={`absolute left-0 top-1/2 transform -translate-y-1/2 w-0.5 h-3/4 rounded-r ${win ? 'bg-[#10b981]' : 'bg-[#ef4444]'}`}></div>
                        <img 
                          src={`https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/${p.championId}.png`} 
                          className="w-8 h-8 rounded-sm border border-[#334155] ml-2"
                          onError={(e) => { e.currentTarget.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg' }}
                          alt=""
                        />
                        <span className="text-[#e2e8f0] font-medium">{champName} <span className="text-yellow-500 text-[10px] ml-1">{stars}</span></span>
                      </td>
                      <td className={`py-2 px-2 font-bold ${win ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                        {win ? 'VICTORIA' : 'DERROTA'}
                      </td>
                      <td className="py-2 px-2 text-[#cbd5e1] font-medium">
                        {st.kills}/{st.deaths}/{st.assists}
                      </td>
                      <td className="py-2 px-2 text-[#94a3b8]">
                        {cs} <span className="text-[10px] opacity-60">({csMin}/m)</span>
                      </td>
                      <td className="py-2 px-2 text-[#94a3b8]">
                        {mins}:{String(secs).padStart(2,'0')}
                      </td>
                      <td className="py-2 px-2 text-[#94a3b8]">{g.gameMode || 'Ranked'}</td>
                      <td className="py-2 px-2 text-[#94a3b8]">{dateStr}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
