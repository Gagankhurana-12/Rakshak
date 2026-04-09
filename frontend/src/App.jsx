import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  FileText,
  Heart,
  LogOut,
  Shield,
  Moon,
  Zap,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import AnalysisChat from "./components/AnalysisChat";
import DiagnosisPanel from "./components/DiagnosisPanel";
import DocumentUpload from "./components/DocumentUpload";
import VitalsCard from "./components/VitalsCard";
import VitalsTrend from "./components/VitalsTrend";
import AuthModal from "./components/AuthModal";
import api, {
  API_BASE_URL,
  analyzeHealth,
  getUserDocuments,
  getVitalsHistory,
  syncVitals,
  uploadDocument,
} from "./services/api";

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [vitalsHistory, setVitalsHistory] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const [loading, setLoading] = useState({
    user: true,
    sync: false,
    analyze: false,
    upload: false,
    history: false,
  });
  const [errorMessage, setErrorMessage] = useState("");

  const authMode =
    location.pathname === "/signup"
      ? "signup"
      : location.pathname === "/login"
        ? "login"
        : null;
  const showAuthModal = !user && authMode !== null;

  const latestVitals = vitalsHistory[vitalsHistory.length - 1] || null;

  const fetchHistory = async (userId) => {
    setLoading((prev) => ({ ...prev, history: true }));
    try {
      const data = await getVitalsHistory(userId, 7);
      setVitalsHistory(data.data || []);
    } catch (error) {
      console.warn("Failed to load vitals history", error);
      setVitalsHistory([]);
    } finally {
      setLoading((prev) => ({ ...prev, history: false }));
    }
  };

  const fetchDocuments = async (userId) => {
    try {
      const data = await getUserDocuments(userId);
      setDocuments(data.documents || []);
    } catch (error) {
      console.warn("Failed to load documents", error);
      setDocuments([]);
    }
  };

  const syncUserData = async (userId) => {
    setLoading((prev) => ({ ...prev, sync: true }));
    try {
      const syncResult = await syncVitals(userId, 7);
      if (syncResult?.synced_at) {
        setLastSyncedAt(syncResult.synced_at);
      }
      await fetchHistory(userId);
    } catch (error) {
      console.warn("Sync failed", error);
    } finally {
      setLoading((prev) => ({ ...prev, sync: false }));
    }
  };

  const hydrateUserDataInBackground = (profile) => {
    if (!profile?.id) {
      return;
    }

    const tasks = profile.is_google_connected
      ? [syncUserData(profile.id), fetchDocuments(profile.id)]
      : [fetchDocuments(profile.id)];

    Promise.allSettled(tasks).catch((error) => {
      console.warn("Background hydration failed", error);
    });
  };

  const checkUser = async (forcedUser = null, tokens = null) => {
    if (forcedUser) {
      setUser(forcedUser);
      localStorage.setItem("rakshak_user_id", forcedUser.id);
      if (tokens) {
        localStorage.setItem("rakshak_access_token", tokens.access);
        localStorage.setItem("rakshak_refresh_token", tokens.refresh);
      }
      navigate("/", { replace: true });
      hydrateUserDataInBackground(forcedUser);
      return;
    }

    const savedId = localStorage.getItem("rakshak_user_id");
    if (!savedId) {
      setUser(null);
      setLoading((prev) => ({ ...prev, user: false }));
      return;
    }

    setLoading((prev) => ({ ...prev, user: true }));
    try {
      console.log("🔍 Checking user session for ID:", savedId);
      const response = await api.get(`/profile?user_id=${savedId}`);
      if (!response.data?.id) {
        throw new Error("No user data returned");
      }
      setUser(response.data);

      if (authMode) {
        navigate("/", { replace: true });
      }

      // Fast-start mode: paint dashboard immediately, hydrate data in background.
      hydrateUserDataInBackground(response.data);
    } catch (error) {
      console.error(
        "❌ Session check failed:",
        error.response?.data || error.message,
      );
      // Only clear session if it's a definitive 401 Unauthorized
      if (error.response?.status === 401) {
        setUser(null);
        localStorage.removeItem("rakshak_user_id");
        localStorage.removeItem("rakshak_access_token");
        localStorage.removeItem("rakshak_refresh_token");
        if (!authMode) {
          navigate("/login", { replace: true });
        }
      }
    } finally {
      setLoading((prev) => ({ ...prev, user: false }));
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlUid = params.get("uid");
    const errorMsg = params.get("message");
    const status = params.get("status");

    if (status === "error" && errorMsg) {
      setErrorMessage(`OAuth Error: ${errorMsg}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlUid) {
      localStorage.setItem("rakshak_user_id", urlUid);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    checkUser();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!user?.id) {
      return undefined;
    }

    const intervalId = setInterval(
      () => {
        syncUserData(user.id);
      },
      5 * 60 * 1000,
    );

    return () => clearInterval(intervalId);
  }, [user?.id]);

  const handleLogout = async () => {
    // Fast local logout first for instant UI response.
    setUser(null);
    localStorage.removeItem("rakshak_user_id");
    localStorage.removeItem("rakshak_access_token");
    localStorage.removeItem("rakshak_refresh_token");
    setAnalysis(null);
    setVitalsHistory([]);
    setDocuments([]);
    setLastSyncedAt(null);
    setErrorMessage("");
    navigate("/login", { replace: true });

    // Best-effort server logout in background.
    api.get("/logout").catch((error) => {
      console.warn("Logout API call failed", error);
    });
  };

  const handleAnalyze = async (query) => {
    if (!user?.id) {
      setErrorMessage(
        "Connect Google Fit first so Rakshak can analyze your real personal data.",
      );
      return;
    }

    setErrorMessage("");
    setLoading((prev) => ({ ...prev, analyze: true }));
    try {
      const result = await analyzeHealth(user.id, query);
      setAnalysis(result);
      fetchHistory(user.id);
    } catch (error) {
      const message =
        error?.response?.data?.detail ||
        "Analysis failed. Sync Google Fit or try again.";
      setErrorMessage(message);
    } finally {
      setLoading((prev) => ({ ...prev, analyze: false }));
    }
  };

  const handleConnectGoogleFit = (link = false) => {
    const nextUrl = encodeURIComponent(window.location.origin);
    window.location.href = `${API_BASE_URL}/auth?next_url=${nextUrl}${link ? "&link=true" : ""}`;
  };

  const handleUpload = async (file) => {
    if (!user?.id) {
      throw new Error("Connect Google Fit first");
    }

    setLoading((prev) => ({ ...prev, upload: true }));
    try {
      const result = await uploadDocument(user.id, file);
      await fetchDocuments(user.id);
      return result;
    } finally {
      setLoading((prev) => ({ ...prev, upload: false }));
    }
  };

  const cardValues = useMemo(
    () => ({
      heart_rate: latestVitals?.heart_rate,
      steps: latestVitals?.steps,
      sleep_hours: latestVitals?.sleep_hours,
      calories: latestVitals?.calories,
    }),
    [latestVitals],
  );

  const trendData = vitalsHistory.map((entry) => ({
    date: entry.date,
    heart_rate: entry.heart_rate,
    steps: entry.steps,
    sleep_hours: entry.sleep_hours,
    calories: entry.calories,
  }));

  const lastSyncLabel = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : latestVitals?.date
      ? new Date(latestVitals.date).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })
      : "Not synced yet";

  if (loading.user) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
          <p className="text-slate-400 font-medium">
            Initializing Rakshak AI...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {showAuthModal && !user && (
        <AuthModal
          mode={authMode || "login"}
          initialError={authMode ? errorMessage : ""}
          onModeChange={(mode) => navigate(`/${mode}`)}
          onLoginSuccess={checkUser}
          onGoogleConnect={() => handleConnectGoogleFit(false)}
        />
      )}
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.18),transparent_42%),radial-gradient(circle_at_80%_0%,rgba(59,130,246,0.18),transparent_35%),linear-gradient(180deg,rgba(2,6,23,1)_0%,rgba(3,7,18,1)_100%)]" />
      <div className="relative mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <nav className="sticky top-4 z-30 mb-8 rounded-3xl border border-slate-800/80 bg-slate-950/70 px-4 py-3 backdrop-blur-xl shadow-2xl shadow-slate-950/40">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-400/30">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <p className="text-lg font-semibold text-white">Rakshak</p>
                <p className="text-xs text-slate-400">
                  Personalized AI health intelligence
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {user ? (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="inline-flex items-center gap-2 rounded-full border border-rose-500/20 bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-200 transition hover:bg-rose-500/15"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:bg-cyan-500"
                >
                  Login / Sign Up
                </button>
              )}
            </div>
          </div>
        </nav>

        <header className="mb-8 grid gap-6 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
          <div className="space-y-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-200">
              <Sparkles className="h-3.5 w-3.5" />
              Real vitals, real history, real analysis
            </span>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              See what your body is saying, using your own baseline.
            </h1>
            <p className="max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
              Rakshak combines Google Fit, uploaded medical history, and
              retrieved medical knowledge to explain symptoms in your own
              context.
            </p>
            {user && !user.is_google_connected && (
              <div className="group relative overflow-hidden rounded-3xl border border-cyan-400/20 bg-cyan-500/10 p-6 transition hover:bg-cyan-500/15">
                <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-white">
                      Unlock Full Analysis
                    </h3>
                    <p className="mt-1 text-sm text-cyan-200/70">
                      Connect Google Fit to sync your personal vitals and enable
                      baseline-aware AI diagnostics.
                    </p>
                  </div>
                  <button
                    onClick={() => handleConnectGoogleFit(true)}
                    className="flex items-center justify-center gap-2 rounded-2xl bg-cyan-500 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-cyan-500/25 transition hover:bg-cyan-400"
                  >
                    Connect Google Fit
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
                <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-cyan-500/10 blur-2xl transition group-hover:bg-cyan-500/20" />
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5 shadow-2xl shadow-slate-950/40 backdrop-blur-xl">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-slate-400">Status</p>
                <p className="text-xl font-semibold text-white">
                  {user ? "Connected" : "Not connected"}
                </p>
              </div>
              <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300 ring-1 ring-cyan-400/20">
                <Activity className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-500">Recent sync</p>
                <p className="mt-1 font-medium text-white">{lastSyncLabel}</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-500">Reports</p>
                <p className="mt-1 font-medium text-white">
                  {documents.length}
                </p>
              </div>
            </div>
          </div>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {errorMessage}
          </div>
        )}

        <section className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <VitalsCard
            title="Heart Rate"
            value={cardValues.heart_rate}
            unit="BPM"
            icon={Heart}
            colorClass="bg-rose-500 shadow-rose-500/20 shadow-lg"
          />
          <VitalsCard
            title="Steps"
            value={cardValues.steps}
            unit="Today"
            icon={Activity}
            colorClass="bg-cyan-500 shadow-cyan-500/20 shadow-lg"
          />
          <VitalsCard
            title="Sleep"
            value={cardValues.sleep_hours}
            unit="Hours"
            icon={Moon}
            colorClass="bg-indigo-500 shadow-indigo-500/20 shadow-lg"
          />
          <VitalsCard
            title="Calories"
            value={cardValues.calories}
            unit="kcal"
            icon={Zap}
            colorClass="bg-amber-500 shadow-amber-500/20 shadow-lg"
          />
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-8">
            <VitalsTrend
              data={trendData}
              metric="heart_rate"
              color="#22d3ee"
              title="Heart Rate Trend"
            />
            <AnalysisChat
              onAnalyze={handleAnalyze}
              isLoading={loading.analyze}
              disabled={!user}
            />
            {analysis ? (
              <DiagnosisPanel diagnosis={analysis} />
            ) : (
              <div className="rounded-3xl border border-slate-800 bg-card p-6 text-slate-400">
                Ask about your symptoms to generate a personalized analysis.
              </div>
            )}
          </div>

          <aside className="space-y-8">
            <DocumentUpload
              onUpload={handleUpload}
              isLoading={loading.upload}
              disabled={!user}
            />

            <div className="rounded-3xl border border-slate-800 bg-card p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-white">
                    Recent Reports
                  </h3>
                  <p className="text-sm text-slate-400">
                    Uploaded medical documents with extracted text stored in
                    Pinecone.
                  </p>
                </div>
                <FileText className="h-5 w-5 text-primary" />
              </div>

              <div className="space-y-3">
                {documents.length === 0 ? (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-400">
                    No documents uploaded yet.
                  </div>
                ) : (
                  documents.map((report) => (
                    <div
                      key={report.id}
                      className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-white">
                            {report.doc_name}
                          </p>
                          <p className="text-xs text-slate-500">
                            {report.chunks_processed} chunks processed
                          </p>
                        </div>
                        <span className="text-xs text-slate-500">
                          {new Date(report.upload_date).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-card p-6">
              <h3 className="mb-3 text-lg font-semibold text-white">
                How it works
              </h3>
              <ul className="space-y-3 text-sm text-slate-400">
                <li>1. Sync Google Fit data into PostgreSQL.</li>
                <li>2. Use your 7-day baseline for personalization.</li>
                <li>
                  3. Retrieve uploaded medical history and disease knowledge
                  when available.
                </li>
                <li>4. Return structured JSON for the hackathon demo.</li>
              </ul>
            </div>
          </aside>
        </section>
      </div>
    </div>
  );
}

export default App;
