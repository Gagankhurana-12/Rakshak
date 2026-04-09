import React from 'react';
import { AlertCircle, CheckCircle2, Info, ArrowRight } from 'lucide-react';

const DiagnosisPanel = ({ diagnosis }) => {
    if (!diagnosis) return null;

    const conditions = diagnosis.conditions || diagnosis.possible_conditions || [];
    const actions = diagnosis.actions || diagnosis.recommendations || [];
    const overallConfidence = diagnosis.confidence || 'low';
    const correlation = diagnosis.vitals_correlation || diagnosis.explanation || 'Insufficient vitals context.';

    const urgencyColors = {
        low: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
        medium: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
        high: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
    };

    const urgencyIcons = {
        low: CheckCircle2,
        medium: Info,
        high: AlertCircle,
    };

    const UrgencyIcon = urgencyIcons[diagnosis.urgency?.toLowerCase()] || Info;

    return (
        <div className="bg-card rounded-2xl border border-slate-800 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className={`p-4 border-b flex items-center justify-between ${urgencyColors[diagnosis.urgency?.toLowerCase()] || urgencyColors.low}`}>
                <div className="flex items-center gap-2">
                    <UrgencyIcon className="w-5 h-5" />
                    <span className="font-semibold uppercase tracking-wider text-sm">
                        {diagnosis.urgency || 'Low'} Priority
                    </span>
                </div>
                <span className="text-xs opacity-70">AI Generated Insight</span>
            </div>

            <div className="p-6 space-y-6">
                <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
                    <span>Confidence</span>
                    <span className="font-semibold text-white capitalize">{overallConfidence}</span>
                </div>

                <div>
                    <h4 className="text-slate-400 text-sm font-medium mb-3 uppercase tracking-tight">Possible Conditions</h4>
                    <div className="space-y-3">
                        {conditions.map((condition, idx) => (
                            <div key={idx} className="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                                <p className="text-white text-sm font-semibold">{condition.name || condition || 'Unknown condition'}</p>
                                <p className="text-slate-400 text-xs mt-1">Confidence: {condition.confidence || 'insufficient data'}</p>
                                <p className="text-slate-300 text-sm mt-2">{condition.reason || 'No specific reason provided.'}</p>
                            </div>
                        ))}
                    </div>
                </div>

                <div>
                    <h4 className="text-slate-400 text-sm font-medium mb-2 uppercase tracking-tight">Vitals Correlation</h4>
                    <p className="text-slate-200 leading-relaxed">{correlation}</p>
                </div>

                <div>
                    <h4 className="text-slate-400 text-sm font-medium mb-3 uppercase tracking-tight">Suggested Actions</h4>
                    <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {actions.map((action, idx) => (
                            <li key={idx} className="flex items-start gap-3 bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                                <ArrowRight className="w-4 h-4 text-primary mt-1 shrink-0" />
                                <span className="text-slate-300 text-sm">{action}</span>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="text-xs text-slate-500 border-t border-slate-800 pt-4">
                    {diagnosis.disclaimer || 'This is not a medical diagnosis'}
                </div>
            </div>
        </div>
    );
};

export default DiagnosisPanel;
