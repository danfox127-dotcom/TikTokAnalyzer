"use client";

import React, { useState } from "react";
import mockData from "@/app/mock-data.json";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Clock,
  Eye,
  FastForward,
  Play,
  Moon,
  Smartphone,
  Globe,
  Activity,
} from "lucide-react";

export function Dashboard({ analysisData }: { analysisData?: any }) {
  const [activeTab, setActiveTab] = useState("overview");

  const tiktokData = mockData.platforms.tiktok;

  const totalVideos = analysisData?.raw_metrics?.total_videos ?? tiktokData.behavioral_analysis.total_videos;
  const username = analysisData?.profile?.username || tiktokData.profile.username;
  const targetLock = analysisData?.target_lock_inferences ?? null;

  const heatmapSource = analysisData?.hourly_heatmap ?? tiktokData.behavioral_analysis.hourly_heatmap;
  const heatmapData = Object.entries(heatmapSource).map(([hour, count]) => ({
    hour: `${hour}:00`,
    views: count as number,
  }));

  const engagementData = [
    { name: "Skipped", value: analysisData?.behavioral_nodes?.skip_count ?? tiktokData.behavioral_analysis.skip_count },
    { name: "Casual", value: analysisData?.behavioral_nodes?.casual_count ?? tiktokData.behavioral_analysis.casual_count },
    { name: "Lingered", value: analysisData?.behavioral_nodes?.linger_count ?? tiktokData.behavioral_analysis.linger_count },
  ];
  const COLORS = ["#ef4444", "#3b82f6", "#22c55e"];

  return (
    <div className="w-full max-w-6xl mx-auto p-4 md:p-6 space-y-8 font-mono bg-black text-emerald-400">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-emerald-500/30">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-emerald-400">
            Algorithmic Mirror
          </h1>
          <p className="text-amber-500 mt-1">
            Analyzing digital footprint for @{username}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold bg-black text-amber-500 border border-amber-500/50 rounded-none uppercase tracking-wider">
            <span className="w-2 h-2 bg-amber-500 animate-pulse"></span>
            Report Generated {new Date(mockData.generated_at).toLocaleDateString()}
          </span>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex space-x-1 border border-emerald-500/30 bg-black p-1 w-fit rounded-none">
        {["overview", "behavior", "interests", "devices"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-bold uppercase tracking-widest transition-colors rounded-none ${
              activeTab === tab
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50"
                : "text-emerald-600 hover:text-emerald-400"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              icon={<Play className="w-5 h-5 text-amber-500" />}
              title="TOTAL_VIDEOS"
              value={totalVideos.toLocaleString()}
            />
            <MetricCard
              icon={<FastForward className="w-5 h-5 text-amber-500" />}
              title="SKIP_RATE"
              value={`${tiktokData.behavioral_analysis.skip_rate}%`}
              subtitle={`${tiktokData.behavioral_analysis.skip_count.toLocaleString()} videos`}
            />
            <MetricCard
              icon={<Eye className="w-5 h-5 text-amber-500" />}
              title="LINGER_RATE"
              value={`${tiktokData.behavioral_analysis.linger_rate}%`}
              subtitle={`${tiktokData.behavioral_analysis.linger_count.toLocaleString()} videos`}
            />
            <MetricCard
              icon={<Moon className="w-5 h-5 text-amber-500" />}
              title="NIGHT_SHIFT_RATIO"
              value={`${tiktokData.behavioral_analysis.night_shift_ratio}%`}
              subtitle="Activity between 11PM and 4AM"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chart: Activity Heatmap */}
            <div className="lg:col-span-2 p-6 bg-black border border-emerald-500/30 rounded-none relative">
              <h3 className="text-lg font-bold mb-6 flex items-center gap-2 tracking-widest text-emerald-500 uppercase">
                <Clock className="w-5 h-5 text-amber-500" /> Hourly Activity Pattern
              </h3>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={heatmapData}>
                    <CartesianGrid strokeDasharray="1 4" vertical={false} stroke="#10b981" opacity={0.2} />
                    <XAxis 
                      dataKey="hour" 
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: '#059669', fontFamily: 'monospace' }}
                      dy={10}
                    />
                    <YAxis 
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: '#059669', fontFamily: 'monospace' }}
                    />
                    <Tooltip 
                      cursor={{ fill: 'rgba(16, 185, 129, 0.1)' }}
                      contentStyle={{ borderRadius: '0', border: '1px solid rgba(16, 185, 129, 0.5)', backgroundColor: 'black', color: '#10b981', fontFamily: 'monospace' }}
                    />
                    <Bar dataKey="views" fill="#f59e0b" radius={[0, 0, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart: Engagement Split */}
            <div className="p-6 bg-black border border-emerald-500/30 rounded-none flex flex-col">
              <h3 className="text-lg font-bold mb-6 flex items-center gap-2 tracking-widest text-emerald-500 uppercase">
                <Activity className="w-5 h-5 text-amber-500" /> Engagement Profile
              </h3>
              <div className="h-[250px] w-full flex-1">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={engagementData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                    >
                      {engagementData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={index === 0 ? "#f59e0b" : index === 1 ? "#10b981" : "#059669"} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '0', border: '1px solid rgba(16, 185, 129, 0.5)', backgroundColor: 'black', color: '#10b981', fontFamily: 'monospace' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-center gap-4 mt-4">
                {engagementData.map((entry, index) => (
                  <div key={entry.name} className="flex items-center gap-1.5 text-sm uppercase tracking-widest">
                    <span className="w-2 h-2 rounded-none border border-emerald-500" style={{ backgroundColor: index === 0 ? "#f59e0b" : index === 1 ? "#10b981" : "#059669" }}></span>
                    <span className="text-emerald-500">{entry.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Behavior Tab */}
      {activeTab === "behavior" && (
        <div className="p-6 border border-emerald-500/30 bg-black">
          <h2 className="text-xl font-bold mb-6 text-emerald-500 uppercase tracking-widest border-b border-emerald-500/30 pb-4">
            <Activity className="inline w-6 h-6 mr-3 text-amber-500" />
            Behavioral Nodes
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <MetricCard
              icon={<FastForward className="w-5 h-5 text-amber-500" />}
              title="SKIP_RATE_PERCENTAGE"
              value={`${analysisData?.behavioral_nodes?.skip_rate_percentage ?? tiktokData.behavioral_analysis.skip_rate}%`}
            />
            <MetricCard
              icon={<Eye className="w-5 h-5 text-amber-500" />}
              title="LINGER_RATE_PERCENTAGE"
              value={`${analysisData?.behavioral_nodes?.linger_rate_percentage ?? tiktokData.behavioral_analysis.linger_rate}%`}
            />
            <MetricCard
              icon={<Moon className="w-5 h-5 text-amber-500" />}
              title="NIGHT_SHIFT_RATIO"
              value={`${analysisData?.behavioral_nodes?.night_shift_ratio ?? tiktokData.behavioral_analysis.night_shift_ratio}%`}
            />
          </div>
        </div>
      )}

      {/* Interests Tab */}
      {activeTab === "interests" && (
        <div className="p-6 border border-emerald-500/30 bg-black">
          <h2 className="text-xl font-bold mb-6 text-emerald-500 uppercase tracking-widest border-b border-emerald-500/30 pb-4">
            <Globe className="inline w-6 h-6 mr-3 text-amber-500" />
            Extracted Psychographic Nodes
          </h2>
          <ul className="space-y-4 font-mono">
            {(analysisData?.interest_clusters || tiktokData.settings_interests).map((interest: string, idx: number) => (
              <li key={idx} className="flex items-center text-emerald-400 text-lg uppercase tracking-wider">
                <span className="text-amber-500 mr-4 font-bold select-none">&gt;</span>
                {interest}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Devices Tab */}
      {activeTab === "devices" && (
        <div className="p-6 border border-emerald-500/30 bg-black">
          <h2 className="text-xl font-bold mb-6 text-emerald-500 uppercase tracking-widest border-b border-emerald-500/30 pb-4">
            <Smartphone className="inline w-6 h-6 mr-3 text-amber-500" />
            Device Fingerprint
          </h2>
          <div className="overflow-x-auto border border-emerald-500/30 bg-black">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-emerald-500/30 text-amber-500/80 text-xs tracking-widest bg-emerald-950/20">
                  <th className="p-4 font-normal uppercase">Type</th>
                  <th className="p-4 font-normal uppercase">Last Active</th>
                </tr>
              </thead>
              <tbody className="font-mono text-sm">
                {(analysisData?.device_fingerprint || []).length > 0 ? (
                  analysisData.device_fingerprint.map((device: any, idx: number) => (
                    <tr key={idx} className="border-b border-emerald-500/10 hover:bg-emerald-900/30 transition-colors">
                      <td className="p-4 text-emerald-400">{device.type}</td>
                      <td className="p-4 text-emerald-600/80">{device.last_active}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2} className="p-8 text-emerald-600/50 uppercase tracking-widest text-center animate-pulse">
                      [ NO_DEVICE_DATA_FOUND ]
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Placeholder for other tabs */}
      {!["overview", "behavior", "interests", "devices"].includes(activeTab) && (
        <div className="p-12 text-center rounded-none border border-dashed border-emerald-500/50 bg-black">
          <p className="text-amber-500 tracking-widest uppercase animate-pulse">
            [ SECTOR_UNAVAILABLE ]
          </p>
        </div>
      )}
    </div>
  );
}

function MetricCard({ icon, title, value, subtitle }: { icon: React.ReactNode, title: string, value: string | number, subtitle?: string }) {
  return (
    <div className="p-5 bg-black border border-emerald-500/30 rounded-none flex flex-col justify-between hover:bg-emerald-950/20 transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-bold text-emerald-500 tracking-widest uppercase">{title}</p>
        <div className="p-2 border border-emerald-500/30 rounded-none bg-black">{icon}</div>
      </div>
      <div className="mt-4">
        <h4 className="text-3xl font-bold tracking-tight text-emerald-400">{value}</h4>
        {subtitle && <p className="text-xs text-amber-500/80 mt-1 uppercase tracking-wider">{subtitle}</p>}
      </div>
    </div>
  );
}
