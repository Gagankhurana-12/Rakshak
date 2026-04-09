import React from 'react';

const VitalsCard = ({ title, value, unit, icon: Icon, colorClass }) => {
    const formattedValue = (() => {
        if (value === null || value === undefined || value === '') {
            return '--';
        }
        if (typeof value !== 'number' || Number.isNaN(value)) {
            return value;
        }
        if (title === 'Heart Rate') {
            return Math.round(value);
        }
        if (title === 'Calories' || title === 'Steps') {
            return Math.round(value);
        }
        if (title === 'Sleep') {
            return value.toFixed(1);
        }
        return Number.isInteger(value) ? value : value.toFixed(1);
    })();

    return (
        <div className="bg-card p-6 rounded-2xl shadow-lg border border-slate-800 transition-all hover:scale-[1.02]">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-slate-400 font-medium text-sm">{title}</h3>
                <div className={`p-2 rounded-lg ${colorClass}`}>
                    <Icon className="w-5 h-5 text-white" />
                </div>
            </div>
            <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-white">{formattedValue}</span>
                <span className="text-slate-500 text-sm">{unit}</span>
            </div>
        </div>
    );
};

export default VitalsCard;
