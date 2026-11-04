"use client";
import {useEffect,useState} from "react";
import {Subject,SubjectGraph,User,GraphNode} from "@/lib/types";
import {api} from "@/lib/api";
import {ArrowRight,Check,BookOpen} from "lucide-react";

export function SkillTreeDag({subject,currentUser,onSelectTopicForTutor}: {
 subject:Subject;currentUser?:User;onSelectTopicForTutor:(id:number)=>void;
}) {
 const [graph,setGraph]=useState<SubjectGraph>({nodes:[],edges:[]});
 const [selected,setSelected]=useState<number|null>(null);
 const [completed,setCompleted]=useState<number[]>([]);
 const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 useEffect(()=>{let alive=true;setLoading(true);setError("");
 Promise.all([api.getSubjectGraph(subject.subject_id),currentUser?api.getCompletedTopics(currentUser.user_id,subject.subject_id):Promise.resolve({completed_topic_ids:[]})])
 .then(([data,done])=>{if(alive){setGraph(data);setSelected(data.nodes[0]?.id||null);setCompleted(done.completed_topic_ids);}})
 .catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};
 },[subject.subject_id,currentUser?.user_id]);
 const node=graph.nodes.find(n=>n.id===selected);
 const before=graph.edges.filter(e=>e.target===selected);
 const after=graph.edges.filter(e=>e.source===selected);
 const link=(id:number)=>{const n=graph.nodes.find(n=>n.id===id);return n&&<button key={id} onClick={()=>setSelected(id)} className="w-full text-left flex items-center justify-between gap-3 rounded-lg border border-zinc-800 p-3 hover:border-orange-500 text-sm"><span>{n.label}</span><ArrowRight size={16} className="shrink-0 text-orange-400"/></button>};
 const location=(n:GraphNode)=>n.start_page?`PDF pages ${n.start_page}–${n.end_page}`:"Course material";
 return <section className="space-y-4 min-w-0">
  <div><p className="text-xs text-orange-400 mb-1">Learning path</p><h1 className="text-xl font-semibold">{subject.subject_name}</h1><p className="text-sm text-zinc-400 mt-1">Chapters follow the book’s order. Links suggest what to study first; you can open any chapter.</p></div>
  {error&&<p role="alert" className="text-red-400">{error}</p>}
  {loading?<p className="text-zinc-400">Loading chapters...</p>:!graph.nodes.length?<p>No chapters are available yet. Upload course material to get started.</p>:
  <div className="grid lg:grid-cols-[minmax(300px,1fr)_minmax(0,1.4fr)] gap-5 items-start">
   <ol aria-label="Chapters in reading order" className="space-y-2 lg:max-h-[calc(100dvh-13rem)] overflow-y-auto pr-1">
    {graph.nodes.map((n,i)=><li key={n.id}><button onClick={()=>setSelected(n.id)} aria-pressed={n.id===selected} className={`w-full flex gap-3 items-center text-left border rounded-xl p-3 ${n.id===selected?"border-orange-500 bg-orange-950/30":"border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}><span className="w-8 h-8 shrink-0 grid place-items-center rounded-full bg-zinc-800 text-orange-300 text-sm">{completed.includes(n.id)?<Check size={16}/>:i+1}</span><span className="min-w-0"><span className="block text-sm font-medium">{n.label.replace(/^\d+\.\s*/, "")}</span><span className="text-xs text-zinc-500">{location(n)}</span></span></button></li>)}
   </ol>
   {node&&<article className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-5 lg:sticky lg:top-4 min-w-0">
    <div><p className="text-xs text-zinc-500 mb-2 flex items-center gap-2"><BookOpen size={14}/>{location(node)}</p><h2 className="text-xl font-semibold">{node.label}</h2>{node.source_file&&<p className="text-xs text-zinc-500 mt-2 break-words">{node.source_file}</p>}</div>
    <button onClick={()=>onSelectTopicForTutor(node.id)} className="rounded-lg bg-orange-500 hover:bg-orange-600 px-4 py-2 text-sm font-medium">Study this chapter <ArrowRight className="inline ml-2" size={16}/></button>
    <div className="border-t border-zinc-800 pt-4 space-y-2"><h3 className="font-medium text-sm">Learn first</h3><p className="text-xs text-zinc-500">{before.some(e=>e.basis==='book_order')?'Suggested prerequisite from the book’s reading order.':before.length?'Prerequisite chapters.':'This is the starting chapter.'}</p>{before.map(e=>link(e.source))}</div>
    <div className="border-t border-zinc-800 pt-4 space-y-2"><h3 className="font-medium text-sm">Continue with</h3>{after.length?after.map(e=>link(e.target)):<p className="text-sm text-zinc-400">You’ve reached the end of this reading path.</p>}</div>
   </article>}
  </div>}
 </section>;
}
