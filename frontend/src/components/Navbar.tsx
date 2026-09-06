'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ShieldAlert, Radio, FileText, UploadCloud, Activity } from 'lucide-react';
import { api } from '../lib/api';
import { HealthStatus } from '../lib/types';
import { formatNavbarEngineLabel } from '@/lib/formatters';

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.getHealth();
        setHealth(data);
        setIsError(false);
      } catch {
        setIsError(true);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health && health.status === 'healthy' && !isError;

  const navLinks = [
    { name: 'Dashboard', href: '/', icon: Activity },
    { name: 'Scan Audio', href: '/detect', icon: UploadCloud },
    { name: 'Call Demo', href: '/call-demo', icon: ShieldAlert },
    { name: 'Audit Log', href: '/detections', icon: Radio },
  ];

  return (
    <header className="w-full border-b border-slate-200 bg-white shadow-xs">
      <div className="max-w-7xl mx-auto flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-200 group-hover:border-indigo-400 group-hover:bg-indigo-100 transition-all">
            <ShieldAlert className="w-5 h-5 text-indigo-600 group-hover:scale-105 transition-transform" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-wide text-slate-900 uppercase">
                SIH26104
              </span>
              <span className="text-xs px-1.5 py-0.2 rounded font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 font-semibold">
                VOICE-GUARD
              </span>
            </div>
            <p className="text-[10px] font-mono text-slate-500 tracking-wider">
              Voice Cloning Detection Platform
            </p>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium tracking-wide transition-all ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                {link.name}
              </Link>
            );
          })}
        </nav>

        {/* System Telemetry & Docs */}
        <div className="flex items-center gap-3">
          {/* Health Status Indicator */}
          <div
            className="flex items-center gap-2 px-2.5 py-1 rounded-full border border-slate-200 bg-slate-100/90 text-[11px] font-mono"
            title={`Backend Status: ${isHealthy ? 'Online' : 'Offline'}, Engine: ${health?.detection_engine || 'unknown'}`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            />
            {isHealthy ? (
              <span className="text-slate-700">
                API ONLINE <span className="text-slate-300">|</span>{' '}
                <span className="text-indigo-600 font-semibold">
                  {formatNavbarEngineLabel(health?.detection_engine, health?.model_version)}
                </span>
              </span>
            ) : (
              <span className="text-red-600 font-semibold">API OFFLINE</span>
            )}
          </div>

          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-mono text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors border border-transparent hover:border-slate-200"
          >
            <FileText className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Swagger API</span>
          </a>
        </div>
      </div>
    </header>
  );
};
