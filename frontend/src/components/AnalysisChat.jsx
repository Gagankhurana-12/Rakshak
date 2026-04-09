import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Send } from 'lucide-react';

const AnalysisChat = ({ onAnalyze, isLoading, disabled }) => {
    const [query, setQuery] = useState('');
    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef(null);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map((result) => result[0].transcript)
                .join(' ');
            setQuery(transcript);
        };

        recognition.onend = () => {
            setIsListening(false);
        };

        recognition.onerror = () => {
            setIsListening(false);
        };

        recognitionRef.current = recognition;

        return () => {
            recognition.abort();
        };
    }, []);

    const toggleVoice = () => {
        if (!recognitionRef.current) {
            return;
        }

        if (isListening) {
            recognitionRef.current.stop();
            setIsListening(false);
            return;
        }

        recognitionRef.current.start();
        setIsListening(true);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!query.trim() || disabled) {
            return;
        }

        await onAnalyze(query.trim());
    };

    return (
        <div className="rounded-3xl border border-slate-800 bg-slate-950/80 backdrop-blur-xl p-6 shadow-2xl shadow-slate-950/40">
            <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                    <h3 className="text-xl font-semibold text-white">Ask Rakshak</h3>
                    <p className="text-sm text-slate-400 mt-1">Use text or voice. Analysis is based on your synced vitals and uploaded history.</p>
                </div>
                <button
                    type="button"
                    onClick={toggleVoice}
                    disabled={disabled}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isListening ? 'border-rose-400/40 bg-rose-500/10 text-rose-300' : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:bg-slate-800'}`}
                >
                    {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                    {isListening ? 'Listening' : 'Voice'}
                </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
                <textarea
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Example: I have a headache and feel tired after poor sleep."
                    className="min-h-36 w-full resize-none rounded-2xl border border-slate-700 bg-slate-950/70 p-4 text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-500/20"
                />

                <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-slate-500">Tip: mention symptoms, timing, and anything that feels different from your normal baseline.</p>
                    <button
                        type="submit"
                        disabled={disabled || isLoading || !query.trim()}
                        className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
                    >
                        {isLoading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <Send className="h-4 w-4" />}
                        {isLoading ? 'Analyzing' : 'Analyze'}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default AnalysisChat;