import React, { useState } from 'react';
import { Upload, FileText, Check, AlertCircle } from 'lucide-react';

const DocumentUpload = ({ onUpload, isLoading, disabled }) => {
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState('idle'); // idle, success, error

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setStatus('idle');
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        try {
            await onUpload(file);
            setStatus('success');
            setFile(null);
            setTimeout(() => setStatus('idle'), 3000);
        } catch (err) {
            setStatus('error');
        }
    };

    return (
        <div className="bg-card p-6 rounded-2xl border border-slate-800">
            <h3 className="text-xl font-semibold text-white mb-4">Medical Documents</h3>

            <div className="flex flex-col gap-4">
                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-slate-700 rounded-xl cursor-pointer hover:border-primary hover:bg-slate-900/50 transition-all">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        <Upload className="w-8 h-8 text-slate-500 mb-2" />
                        <p className="text-sm text-slate-400">
                            {file ? file.name : <span className="font-semibold text-primary">Click to upload</span>}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">PDF, JPG, PNG (Max 10MB)</p>
                    </div>
                    <input type="file" className="hidden" onChange={handleFileChange} accept=".pdf,image/*" />
                </label>

                <button
                    onClick={handleUpload}
                        disabled={!file || isLoading || disabled}
                    className="w-full bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-white py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 border border-slate-700"
                >
                    {isLoading ? (
                        <div className="w-5 h-5 border-2 border-slate-600 border-t-white rounded-full animate-spin" />
                    ) : status === 'success' ? (
                        <Check className="w-5 h-5 text-emerald-500" />
                    ) : status === 'error' ? (
                        <AlertCircle className="w-5 h-5 text-rose-500" />
                    ) : (
                        <FileText className="w-5 h-5" />
                    )}
                    {status === 'success' ? 'Uploaded!' : status === 'error' ? 'Failed' : 'Upload Document'}
                </button>
            </div>
        </div>
    );
};

export default DocumentUpload;
