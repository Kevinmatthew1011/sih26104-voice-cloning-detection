import React from 'react';
import { ShieldCheck, Cpu, Database, Server } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-800/80 bg-slate-950/60 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
            <span className="text-xs text-slate-400 font-mono">
              Smart India Hackathon (SIH 2026) • Problem Statement SIH26104
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
            <span className="flex items-center gap-1">
              <Server className="w-3 h-3 text-slate-400" /> FastAPI
            </span>
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3 text-slate-400" /> PostgreSQL
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="w-3 h-3 text-cyan-400" /> Modular ML Interface
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};
