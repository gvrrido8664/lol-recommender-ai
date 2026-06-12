import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export default function CoachingView() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get('/perfil');
        if (response.data.status === 'success') {
          setData(response.data.data);
        } else {
          setError(response.data.message || 'Error desconocido');
        }
      } catch (err: any) {
        setError(err.message || 'Error de red');
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-accentTeal border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-4 text-textMuted font-bold tracking-wider">GENERANDO ANÁLISIS DE COACHING...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-accentRed font-bold">
        {error}
      </div>
    );
  }

  if (!data || !data.coaching_report) return null;

  const { coaching_report } = data;

  return (
    <div className="flex flex-col items-center px-4 pb-12">
      {/* Contenedor tipo "Documento Notion" */}
      <div className="w-full max-w-4xl bg-[#0b0f19] border border-[#1e293b] rounded-2xl shadow-2xl p-10 mt-6 relative">
        
        {/* Glow Header */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#a78bfa] to-[#3b82f6]"></div>
        
        {/* Título */}
        <div className="mb-10 text-center">
          <div className="text-6xl mb-4">🎓</div>
          <h1 className="text-3xl font-extrabold text-textWhite tracking-tight mb-2">Auditoría de Coaching Pro</h1>
          <p className="text-textMuted text-sm">Análisis de rendimiento, consistencia y hábitos generados por IA</p>
        </div>

        {/* Resumen Principal */}
        <div className="bg-[#131b2f] rounded-xl p-6 mb-10 border border-[#1e293b]">
          <div dangerouslySetInnerHTML={{ __html: coaching_report.resumen }} />
        </div>

        {/* Feed de Secciones */}
        <div className="space-y-12">
          {coaching_report.secciones.map((sec: any, i: number) => {
            // Ajustamos opacidades para dar ese look suave y premium (Notion-like dark mode)
            const rgbColor = sec.color; 
            
            return (
              <div key={i} className="group relative">
                <div 
                  className="absolute -left-4 top-1 bottom-0 w-1 rounded-full opacity-50 group-hover:opacity-100 transition-opacity"
                  style={{ backgroundColor: rgbColor }}
                ></div>
                
                <h2 className="text-xl font-bold mb-4 flex items-center tracking-wide" style={{ color: rgbColor }}>
                  <span className="text-2xl mr-3 opacity-90">{sec.icono}</span>
                  {sec.titulo}
                </h2>
                
                {/* Contenido HTML de la sección */}
                <div 
                  className="prose prose-invert max-w-none prose-p:text-[#cbd5e1] prose-li:text-[#cbd5e1] prose-strong:text-white"
                  dangerouslySetInnerHTML={{ __html: sec.html }} 
                />
              </div>
            );
          })}
        </div>

        {/* Consejo Final Destacado */}
        <div className="mt-16 relative">
          <div className="absolute inset-0 bg-gradient-to-br from-[#1e1b4b] to-[#0f172a] rounded-xl transform -skew-y-1"></div>
          <div className="relative bg-[#1e1b4b] bg-opacity-60 backdrop-blur-md rounded-xl p-8 border border-[#4c1d95] shadow-[0_0_30px_rgba(76,29,149,0.2)]">
            <h3 className="text-lg font-bold text-[#a855f7] mb-3 flex items-center">
              <span className="mr-2">💡</span> NOTA FINAL DEL COACH
            </h3>
            <p className="text-sm text-[#e2e8f0] leading-relaxed italic">
              "{coaching_report.consejo_final}"
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}
