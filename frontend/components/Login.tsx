"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { User } from "@/lib/types";

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 grid place-items-center p-6">
      <form
        className="w-full max-w-md space-y-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-8"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            onLogin(await api.login(email.trim(), password));
          } catch (e: any) {
            setError(e.message || "Invalid email or password.");
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="text-sm text-orange-400 font-semibold tracking-tight">Chapter1</p>
        <h1 className="text-3xl font-semibold">Welcome back</h1>
        <p className="text-sm text-zinc-400">
          Sign in to explore your courses and continue learning.
        </p>
        <label className="block text-sm">
          Email
          <input
            required
            type="text"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 w-full p-3 rounded-lg bg-zinc-950 border border-zinc-700 focus:outline-none focus:border-orange-500 text-zinc-100"
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            required
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 w-full p-3 rounded-lg bg-zinc-950 border border-zinc-700 focus:outline-none focus:border-orange-500 text-zinc-100"
          />
        </label>
        {error && (
          <p role="alert" className="text-red-400 text-sm">
            {error}
          </p>
        )}
        <button
          disabled={busy}
          className="w-full rounded-lg p-3 bg-orange-500 hover:bg-orange-600 font-semibold disabled:opacity-50 transition-colors shadow-sm shadow-orange-500/20"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
