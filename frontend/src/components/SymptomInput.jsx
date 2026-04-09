import React, { useState } from 'react';
import { Search } from 'lucide-react';

const SymptomInput = ({ onAnalyze, isLoading }) => {
    const [symptoms, setSymptoms] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (symptoms.trim()) {
            onAnalyze(symptoms);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="bg-card p-6 rounded-2xl border border-slate-800">
            <h3 className="text-xl font-semibold text-white mb-4">Symptom Checker</h3>
            <div className="relative">
                <textarea
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary h-32 resize-none transition-all"
                    placeholder="Describe how you're feeling (e.g., I have a headache and a mild fever since morning)..."
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                />
                <button
                    type="submit"
                    disabled={isLoading || !symptoms.trim()}
                    className="absolute bottom-4 right-4 bg-primary hover:bg-blue-600 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors shadow-lg shadow-blue-500/20"
                >
                    {isLoading ? (
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                        <Search className="w-4 h-4" />
                    )}
                    Analyze
                </button>
            </div>
        </form>
    );
};

export default SymptomInput;
