"use client";
import {useEffect,useState} from "react";
import {User,Subject} from "@/lib/types";
import {api} from "@/lib/api";
import {Navbar} from "@/components/Navbar";
import {Login} from "@/components/Login";
import {SkillTreeDag} from "@/components/SkillTreeDag";
import {TutorChat} from "@/components/TutorChat";
import {DocumentUpload} from "@/components/DocumentUpload";
import {VectorStoreManager} from "@/components/VectorStoreManager";
export default function Home() {
 const [user,setUser]=useState<User|null>(null);const [ready,setReady]=useState(false);const [subjects,setSubjects]=useState<Subject[]>([]);
 const [subjectId,setSubjectId]=useState(0);const [topicId,setTopicId]=useState<number|null>(null);const [error,setError]=useState("");
 const [activeTab,setActiveTab]=useState<"upload"|"skilltree"|"tutor"|"vectors">("upload");
 const [hasDocument,setHasDocument]=useState(false);
 useEffect(()=>{api.me().then(setUser).catch(()=>{}).finally(()=>setReady(true));const expired=()=>setUser(null);window.addEventListener("auth-expired",expired);return()=>window.removeEventListener("auth-expired",expired);},[]);
 const refresh=async()=>{try{const rows=await api.getSubjects();setSubjects(rows);setHasDocument(rows.some(s=>!!s.is_indexed));setSubjectId(id=>rows.some(s=>s.subject_id===id)?id:(rows[0]?.subject_id||0));setError("");}catch(e:any){setError(e.message);}};
 useEffect(()=>{if(user){setActiveTab("upload");setTopicId(null);refresh();}else{setSubjects([]);setSubjectId(0);}},[user]);
 const logout=async()=>{try{await api.logout();setUser(null);}catch(e:any){setError(e.message);}};
 if(!ready) return <main className="min-h-screen bg-zinc-950 text-zinc-300 grid place-items-center">Loading...</main>;
 if(!user) return <Login onLogin={setUser}/>;
 const subject=subjects.find(s=>s.subject_id===subjectId);
 return <div className={`app-shell bg-zinc-950 text-zinc-100 ${activeTab === "tutor" ? "app-shell-chat" : ""}`}><Navbar currentUser={user} onLogout={logout} activeTab={activeTab} setActiveTab={setActiveTab} hasDocument={hasDocument}/>
 <main className="app-main">{error&&<p role="alert" className="text-red-400">{error}</p>}
 {activeTab==="upload"&&(user.role!=="student"?<DocumentUpload subjects={subjects} activeSubjectId={subjectId} onSubjectChange={setSubjectId} onSubjectCreated={s=>{setSubjectId(s.subject_id);refresh();}} onProceedToSkillTree={()=>setActiveTab("skilltree")} onProceedToTutor={()=>setActiveTab("tutor")} hasDocument={hasDocument} setHasDocument={setHasDocument} currentUser={user} onDeleteSubject={()=>refresh()}/>:<section className="space-y-4"><h1 className="text-2xl font-semibold">Your courses</h1><div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">{subjects.map(s=><button key={s.subject_id} className="text-left rounded-xl border border-zinc-800 bg-zinc-900 p-5" onClick={()=>{setSubjectId(s.subject_id);setTopicId(null);setActiveTab("skilltree");}}><span className="block font-semibold">{s.subject_name}</span><span className="text-sm text-zinc-400">{s.total_topics} chapters · Open learning path</span></button>)}</div>{!subjects.length&&<p>Your instructor has not uploaded course material yet.</p>}</section>)}
 {activeTab==="skilltree"&&subject&&<SkillTreeDag key={subjectId} subject={subject} currentUser={user} onSelectTopicForTutor={id=>{setTopicId(id);setActiveTab("tutor");}}/>}
 {activeTab==="tutor"&&subject&&<TutorChat key={`${user.user_id}-${subjectId}`} currentUser={user} subjects={subjects} activeSubjectId={subjectId} initialTopicId={topicId} onSubjectChange={id=>{setSubjectId(id);setTopicId(null);}}/>}
 {activeTab==="vectors"&&user.role==="admin"&&<VectorStoreManager subject={subject}/>}
 </main></div>;
}
