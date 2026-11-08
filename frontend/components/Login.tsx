"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { User } from "@/lib/types";
import { GraduationCap, BookOpen, ShieldCheck } from "lucide-react";

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSignIn = async (ident: string, pass: string) => {
    setBusy(true);
    setError("");
    try {
      const u = await api.login(ident, pass);
      onLogin(u);
    } catch (e: any) {
      setError(e.message || "Failed to sign in. Please verify your credentials.");
    } finally {
      setBusy(false);
    }
  };

  const handleQuickLogin = (roleIdent: string) => {
    const roleEmail = `${roleIdent}@chapter1.edu`;
    const defaultPass = "password123";
    setEmail(roleEmail);
    setPassword(defaultPass);
    handleSignIn(roleIdent, defaultPass);
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 grid place-items-center p-6">
      <div className="w-full max-w-md space-y-6">
        <form
          className="space-y-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-xl"
          onSubmit={(e) => {
            e.preventDefault();
            handleSignIn(email, password);
          }}
        >
          <div>
            <p className="text-sm text-orange-400 font-semibold tracking-tight">Chapter1</p>
            <h1 className="text-2xl font-bold text-zinc-100 mt-1">Sign In</h1>
            <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
              Access your interactive learning path, skill tree, and slide knowledge base.
            </p>
          </div>

          {/* 1-Click Quick Demo Switcher */}
          <div className="space-y-2 pt-1">
            <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider block">
              1-Click Demo Profiles
            </span>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("student")}
                className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-zinc-800 bg-zinc-950 hover:bg-zinc-800/80 hover:border-emerald-500/50 transition-all text-xs group"
              >
                <GraduationCap className="h-4 w-4 text-emerald-400 mb-1 group-hover:scale-110 transition-transform" />
                <span className="font-semibold text-zinc-200">Student</span>
                <span className="text-[9px] text-zinc-500">Learner</span>
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("instructor")}
                className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-zinc-800 bg-zinc-950 hover:bg-zinc-800/80 hover:border-amber-500/50 transition-all text-xs group"
              >
                <BookOpen className="h-4 w-4 text-amber-400 mb-1 group-hover:scale-110 transition-transform" />
                <span className="font-semibold text-zinc-200">Instructor</span>
                <span className="text-[9px] text-zinc-500">Teacher</span>
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("admin")}
                className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-zinc-800 bg-zinc-950 hover:bg-zinc-800/80 hover:border-orange-500/50 transition-all text-xs group"
              >
                <ShieldCheck className="h-4 w-4 text-orange-400 mb-1 group-hover:scale-110 transition-transform" />
                <span className="font-semibold text-zinc-200">Admin</span>
                <span className="text-[9px] text-zinc-500">Root</span>
              </button>
            </div>
          </div>

          <div className="relative my-2">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-zinc-800" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase">
              <span className="bg-zinc-900 px-2 text-zinc-500">or enter credentials</span>
            </div>
          </div>

          <label className="block text-xs font-medium text-zinc-300">
            Email or Username
            <input
              required
              type="text"
              autoComplete="username"
              placeholder="e.g. student, admin, or email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full p-2.5 text-xs rounded-lg bg-zinc-950 border border-zinc-700/80 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500 transition-colors"
            />
          </label>

          <label className="block text-xs font-medium text-zinc-300">
            Password
            <input
              required
              type="password"
              autoComplete="current-password"
              placeholder="e.g. password123 or access token"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full p-2.5 text-xs rounded-lg bg-zinc-950 border border-zinc-700/80 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500 transition-colors"
            />
          </label>

          {error && (
            <p role="alert" className="text-red-400 text-xs bg-red-950/30 border border-red-900/50 rounded-lg p-2.5">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg p-2.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold disabled:opacity-50 transition-colors shadow-sm shadow-orange-500/20"
          >
            {busy ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p className="text-center text-[11px] text-zinc-500">
          Demo Password: <code className="text-zinc-400 font-mono">password123</code> for all roles
        </p>
      </div>
    </main>
  );
}
