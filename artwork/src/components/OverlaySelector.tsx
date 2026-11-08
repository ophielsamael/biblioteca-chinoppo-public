import React from 'react';

export const overlayOptions = [
  "UHDBD with HDR and Atmos",
  "UHDBD with DV and Atmos",
  "UHDBD with HDR and DTS",
  "UHDBD with DV and DTS",
  "UHDBD with DV and Imax",
  "UHDBD with DV",
  "UHDBD with HDR",
  "UHDBD with HDR and Imax",
  "UHDBD with HDR10+",
  "UHDBD with HDR10+ and Imax",
  "UHDBD with Imax",
  "UHDBD",
  "BD with DV and Imax",
  "BD with DV",
  "BD with HDR",
  "BD with HDR and Imax",
  "BD with HDR10+",
  "BD with HDR10+ and Imax",
  "BD with Imax",
  "BD 3D",
  "BD 3D with IMAX",
  "BD",
  "DTheater"
];

interface OverlaySelectorProps {
  value: string | null;
  onChange: (value: string | null) => void;
  t: any;
}

export default function OverlaySelector({ value, onChange, t }: OverlaySelectorProps) {
  return (
    <div className="flex flex-col gap-3 w-full">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t.bannersAndOverlays}</span>
      
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
        className="w-full bg-[#11131c] border border-white/10 rounded-xl px-4 py-3 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-[#52b54b]/50 hover:bg-[#1a1c24] cursor-pointer transition-all appearance-none"
        style={{ 
          backgroundImage: 'url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'white\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3e%3cpolyline points=\'6 9 12 15 18 9\'%3e%3c/polyline%3e%3c/svg%3e")', 
          backgroundRepeat: 'no-repeat', 
          backgroundPosition: 'right 1rem center', 
          backgroundSize: '1em' 
        }}
      >
        <option value="">{t.noOverlay}</option>
        {overlayOptions.map(opt => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>

      <p className="text-xs text-gray-500 mt-1 px-1">
        {t.selectOverlayDesc}
      </p>
    </div>
  );
}
