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
 if(!ready) return <main className="min-h-screen bg-zinc-950 text-zinc-300 grid place-items-center">Loadingâ€¦</main>;
 if(!user) return <Login onLogin={setUser}/>;
 const subject=subjects.find(s=>s.subject_id===subjectId);
 return <div className="min-h-screen bg-zinc-950 text-zinc-100"><Navbar currentUser={user} onLogout={logout} activeTab={activeTab} setActiveTab={setActiveTab} hasDocument={hasDocument}/>
 <main className="max-w-7xl mx-auto p-4 sm:p-8 space-y-4">{error&&<p role="alert" className="text-red-400">{error}</p>}
 {subjects.length>0&&<label className="flex gap-3 items-center text-sm text-zinc-400">Course<select aria-label="Course" value={subjectId} onChange={e=>{setSubjectId(Number(e.target.value));setTopicId(null);}} className="bg-zinc-900 border border-zinc-700 rounded-lg p-2 max-w-full">{subjects.map(s=><option key={s.subject_id} value={s.subject_id}>{s.subject_name}</option>)}</select></label>}
 {activeTab==="upload"&&(user.role!=="student"?<DocumentUpload subjects={subjects} activeSubjectId={subjectId} onSubjectChange={setSubjectId} onSubjectCreated={s=>{setSubjectId(s.subject_id);refresh();}} onProceedToSkillTree={()=>setActiveTab("skilltree")} onProceedToTutor={()=>setActiveTab("tutor")} hasDocument={hasDocument} setHasDocument={setHasDocument} currentUser={user} onDeleteSubject={()=>refresh()}/>:<section className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 space-y-4"><h1 className="text-2xl font-semibold">Your learning space</h1><p className="text-zinc-400">{subject?"Choose a course above, then explore its concepts or continue with your tutor.":"Your instructor has not uploaded course material yet."}</p>{subject&&<button className="bg-orange-500 rounded-lg px-4 py-2" onClick={()=>setActiveTab("tutor")}>Continue learning</button>}</section>)}
 {activeTab==="skilltree"&&subject&&<SkillTreeDag key={subjectId} subject={subject} currentUser={user} onSelectTopicForTutor={id=>{setTopicId(id);setActiveTab("tutor");}}/>}
 {activeTab==="tutor"&&subject&&<TutorChat key={`${user.user_id}-${subjectId}`} currentUser={user} subjects={subjects} activeSubjectId={subjectId} initialTopicId={topicId} onSubjectChange={id=>{setSubjectId(id);setTopicId(null);}}/>}
 {activeTab==="vectors"&&user.role==="admin"&&<VectorStoreManager currentUser={user} onSwitchToAdmin={()=>{}} onCoursesUpdated={refresh}/>}
 </main></div>;
}
