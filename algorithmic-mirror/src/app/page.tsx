"use client";

import { useState } from "react";
import { Dashboard } from "@/components/dashboard/Dashboard";

export default function Home() {
  const [isMachineView, setIsMachineView] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [profileData, setProfileData] = useState(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      // Hitting the Python brain on port 8001!
      const response = await fetch("http://localhost:8001/api/analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      
      if (data.status === "success") {
        setProfileData(data);
        setIsMachineView(true); // TRIGGER THE HUD
      } else {
        alert("System error analyzing payload.");
      }
    } catch (error) {
      console.error("Uplink failed:", error);
      alert("Failed to connect to the Python backend on port 8001.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className={`min-h-screen w-full transition-colors duration-500 ${isMachineView ? 'bg-black text-emerald-400 font-mono' : 'bg-slate-50 text-slate-900'}`}>
      
      {/* HEADER */}
      <header className={`p-6 border-b ${isMachineView ? 'border-emerald-500/30' : 'border-slate-200'} flex justify-between items-center`}>
        <h1 className="text-2xl font-bold tracking-tighter">
          {isMachineView ? "SYSTEM // GHOST_PROFILE" : "TikTok Analyzer"}
        </h1>
        <button 
          onClick={() => setIsMachineView(!isMachineView)}
          className={`px-4 py-2 text-sm font-bold ${isMachineView ? 'bg-emerald-500/10 border border-emerald-500 text-emerald-400 hover:bg-emerald-500/20' : 'bg-black text-white rounded-full hover:bg-slate-800'}`}
        >
          {isMachineView ? "[ DISABLE X-RAY ]" : "Reveal Machine View"}
        </button>
      </header>

      {/* BODY */}
      <div className="p-8 max-w-6xl mx-auto">
        {!isMachineView ? (
          <div className="text-center mt-20 space-y-6 flex flex-col items-center">
            <h2 className="text-3xl font-semibold">Welcome to your data dashboard.</h2>
            <p className="text-slate-500">Upload your JSON file to see your insights in a clean, friendly environment.</p>
            
            {/* THE DROPZONE */}
            <div className="mt-8 p-8 border-2 border-dashed border-slate-300 rounded-2xl bg-white w-full max-w-md hover:border-slate-400 transition-colors">
              <input 
                type="file" 
                accept=".json" 
                onChange={handleFileUpload} 
                className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-slate-50 file:text-slate-700 hover:file:bg-slate-100 cursor-pointer"
                disabled={isLoading}
              />
              {isLoading && <p className="text-sm text-slate-400 mt-4 animate-pulse">Analyzing behavioral nodes...</p>}
            </div>
            
          </div>
        ) : (
          <div className="border border-emerald-500/30 p-6 bg-black shadow-[0_0_15px_rgba(16,185,129,0.1)]">
            <p className="text-emerald-500/50 mb-6 text-sm">&gt; INITIATING HUD...</p>
            <Dashboard analysisData={profileData} />
          </div>
        )}
      </div>
    </main>
  );
}