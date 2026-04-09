import React, { useEffect, useState } from "react";
import { Shield, Mail, Lock, User, ArrowRight, Activity } from "lucide-react";
import api from "../services/api";

const AuthModal = ({
  onLoginSuccess,
  onGoogleConnect,
  mode = "login",
  onModeChange,
  initialError = "",
}) => {
  const [isSignup, setIsSignup] = useState(mode === "signup");
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    name: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(initialError);

  useEffect(() => {
    setIsSignup(mode === "signup");
  }, [mode]);

  useEffect(() => {
    if (initialError) setError(initialError);
  }, [initialError]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const endpoint = isSignup ? "/signup" : "/login";
      console.log(`Sending authentication request to: ${API_BASE_URL}${endpoint}`);
      console.log("Request Payload:", { ...formData, password: "[REDACTED]" });
      
      const response = await api.post(endpoint, formData);
      console.log("Authentication successful, response:", response.data);
      
      if (response.data.status === "success") {
        onLoginSuccess(
          {
            id: response.data.user_id,
            display_name: formData.name || formData.email.split("@")[0],
            email: formData.email,
            is_google_connected: response.data.is_google_connected || false,
          },
          {
            access: response.data.access_token,
            refresh: response.data.refresh_token,
          },
        );
      } else {
        console.warn("Authentication failed, expected 'success' status:", response.data);
      }
    } catch (err) {
      console.error("AXIOS ERROR IN AUTH:", err);
      console.error("Error Response Data:", err.response?.data);
      console.error("Error Status:", err.response?.status);
      console.error("Error Headers:", err.response?.headers);
      
      const errorMessage = err.response?.data?.detail 
        || (err.message === "Network Error" ? "Network error - Backend might be unreachable or CORS policy blocked the request." : "Authentication failed");
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md px-4">
      <div className="w-full max-w-md overflow-hidden rounded-3xl border border-slate-800 bg-slate-900 shadow-2xl">
        <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 p-8 text-center border-b border-slate-800">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-400/30">
            <Shield className="h-8 w-8" />
          </div>
          <h2 className="text-2xl font-bold text-white">Welcome to Rakshak</h2>
          <p className="mt-2 text-sm text-slate-400">
            Personalized AI Health Intelligence
          </p>
        </div>

        <div className="p-8">
          {error && (
            <div className="mb-4 rounded-xl bg-rose-500/10 border border-rose-500/20 p-3 text-sm text-rose-300">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <button
              onClick={onGoogleConnect}
              className="flex w-full items-center justify-center gap-3 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              <Activity className="h-5 w-5 text-cyan-600" />
              Continue with Google Fit
            </button>

            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-slate-800"></div>
              <span className="mx-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Or use email
              </span>
              <div className="flex-grow border-t border-slate-800"></div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isSignup && (
                <div className="relative">
                  <User className="absolute left-3 top-3 h-5 w-5 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Full Name"
                    className="w-full rounded-2xl border border-slate-800 bg-slate-950/50 py-2.5 pl-10 pr-4 text-sm text-white focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    required={isSignup}
                  />
                </div>
              )}
              <div className="relative">
                <Mail className="absolute left-3 top-3 h-5 w-5 text-slate-500" />
                <input
                  type="email"
                  placeholder="Email Address"
                  className="w-full rounded-2xl border border-slate-800 bg-slate-950/50 py-2.5 pl-10 pr-4 text-sm text-white focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  required
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-5 w-5 text-slate-500" />
                <input
                  type="password"
                  placeholder="Password"
                  className="w-full rounded-2xl border border-slate-800 bg-slate-950/50 py-2.5 pl-10 pr-4 text-sm text-white focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-50"
              >
                {loading
                  ? "Processing..."
                  : isSignup
                    ? "Create Account"
                    : "Sign In"}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-500">
              {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
              <button
                onClick={() => {
                  const nextMode = isSignup ? "login" : "signup";
                  if (onModeChange) {
                    onModeChange(nextMode);
                  } else {
                    setIsSignup(!isSignup);
                  }
                }}
                className="font-semibold text-cyan-400 hover:text-cyan-300"
              >
                {isSignup ? "Sign In" : "Sign Up"}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthModal;
