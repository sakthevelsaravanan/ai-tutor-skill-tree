"use client";
import { User } from "@/lib/types";
type Tab = "upload" | "skilltree" | "tutor" | "vectors";
export function Navbar({currentUser,onLogout,activeTab,setActiveTab,hasDocument}: {currentUser:User;onLogout:()=>void;activeTab:Tab;setActiveTab:(tab:Tab)=>void;hasDocument:boolean}) {
  const items: Array<[Tab,string]> = [["upload","Courses"],["skilltree","Skill tree"],["tutor","Tutor"]];
  if (currentUser.role === "admin") items.push(["vectors","Knowledge base"]);
  return <header className="border-b border-zinc-800 bg-zinc-950 px-4 sm:px-6 py-3"><div className="app-nav flex flex-wrap items-center justify-between gap-3">
    <div><span className="font-bold text-orange-400">AI Tutor</span><p className="hidden xl:block text-xs text-zinc-500">Learn from your course materials</p></div>
    <nav className="app-tabs flex gap-2">{items.map(([id,label])=><button key={id} onClick={()=>setActiveTab(id)} disabled={!hasDocument && (id==="skilltree" || id==="tutor")} className={`px-3 py-2 rounded-lg text-sm disabled:opacity-30 ${activeTab===id ? "bg-orange-500 text-white" : "bg-zinc-900 text-zinc-300"}`}>{label}</button>)}</nav>
    <div className="flex gap-3 items-center text-xs text-zinc-400"><span>{currentUser.full_name} · {currentUser.role}</span><button onClick={onLogout} className="border border-zinc-700 rounded-lg px-3 py-2">Sign out</button></div>
  </div></header>;
}
