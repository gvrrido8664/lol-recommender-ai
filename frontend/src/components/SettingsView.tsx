import React from 'react';

const SettingsView: React.FC = () => {
  return (
    <div className="flex flex-col h-full bg-bgPanel p-6 rounded-xl border border-borderSubtle">
      <h2 className="text-2xl font-bold text-textWhite mb-6">Configuración</h2>
      
      <div className="space-y-6">
        <div className="bg-bgDark p-5 rounded-lg border border-borderSubtle">
          <h3 className="text-lg font-semibold text-textGold mb-4">Rutas del Juego</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-textMuted mb-1">Ruta de instalación de League of Legends</label>
              <input 
                type="text" 
                className="w-full bg-bgPanel border border-borderSubtle rounded-md py-2 px-3 text-textWhite focus:outline-none focus:border-accentTeal transition-colors"
                defaultValue="C:\Riot Games\League of Legends"
              />
            </div>
          </div>
        </div>

        <div className="bg-bgDark p-5 rounded-lg border border-borderSubtle">
          <h3 className="text-lg font-semibold text-textGold mb-4">Preferencias de Recomendador</h3>
          <div className="space-y-3">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input type="checkbox" className="form-checkbox h-5 w-5 text-accentTeal rounded bg-bgPanel border-borderSubtle focus:ring-accentTeal focus:ring-offset-bgDark" defaultChecked />
              <span className="text-textWhite">Habilitar Auto-Importar Runas</span>
            </label>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input type="checkbox" className="form-checkbox h-5 w-5 text-accentTeal rounded bg-bgPanel border-borderSubtle focus:ring-accentTeal focus:ring-offset-bgDark" defaultChecked />
              <span className="text-textWhite">Habilitar Auto-Importar Objetos Core</span>
            </label>
          </div>
        </div>
      </div>
      
      <div className="mt-auto pt-6 flex justify-end">
        <button className="bg-accentTeal hover:bg-teal-400 text-bgDark font-bold py-2 px-6 rounded-md transition-colors shadow-[0_0_10px_rgba(45,212,191,0.3)] hover:shadow-[0_0_15px_rgba(45,212,191,0.5)]">
          Guardar Cambios
        </button>
      </div>
    </div>
  );
};

export default SettingsView;
