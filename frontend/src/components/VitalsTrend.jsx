import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const VitalsTrend = ({ data, metric, color, title }) => {
    if (!data || data.length === 0) {
        return (
            <div className="bg-card p-6 rounded-2xl border border-slate-800 h-75 flex items-center justify-center">
                <p className="text-slate-500">No trend data available</p>
            </div>
        );
    }

    return (
        <div className="bg-card p-6 rounded-2xl border border-slate-800">
            <h3 className="text-xl font-semibold text-white mb-6">{title}</h3>
            <div className="h-62.5 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <defs>
                            <linearGradient id={`color-${metric}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={color} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis
                            dataKey="date"
                            stroke="#64748b"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(str) => new Date(str).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                        />
                        <YAxis
                            stroke="#64748b"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(val) => val === 0 ? '' : val}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                            itemStyle={{ color: '#f8fafc' }}
                        />
                        <Area
                            type="monotone"
                            dataKey={metric}
                            stroke={color}
                            fillOpacity={1}
                            fill={`url(#color-${metric})`}
                            strokeWidth={3}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default VitalsTrend;
