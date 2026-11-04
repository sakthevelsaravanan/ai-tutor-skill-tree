"use client";
import {useEffect,useState} from "react";
import {api} from "@/lib/api";

export function MasteryPanel({userId,subjectId,topicId,ensureSession,onSelectTopic,disabled}: {
 userId:number;subjectId:number;topicId:number|null;ensureSession:()=>Promise<string>;
 onSelectTopic:(id:number)=>void;disabled:boolean;
}) {
 const [mastery,setMastery]=useState<Awaited<ReturnType<typeof api.mastery>>|null>(null);
 const [recommendation,setRecommendation]=useState<Awaited<ReturnType<typeof api.recommendation>>|null>(null);
 const [mcq,setMcq]=useState(0);const [check,setCheck]=useState(1);
 const [verdict,setVerdict]=useState("PARTIAL");const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [saved,setSaved]=useState("");
 const refresh=async()=>{const [m,r]=await Promise.all([api.mastery(userId,subjectId),api.recommendation(userId,subjectId)]);setMastery(m);setRecommendation(r);};
 useEffect(()=>{refresh().catch(e=>setError(e.message));},[userId,subjectId]);
 useEffect(()=>{setSaved("");setMcq(0);setCheck(1);setVerdict("PARTIAL");},[topicId]);
 const current=mastery?.topics.find(t=>t.topic_id===topicId);
 return <details className="border-t border-zinc-800 bg-zinc-900/60 px-4 py-3 text-xs">
 <summary className="cursor-pointer text-zinc-300">Your progress: {Number(mastery?.mastery_percentage||0).toFixed(0)}% mastered · {current?.mastery_status.replaceAll("_"," ").toLowerCase()||"untouched"} · Self-assessment</summary>
 <div className="pt-3 space-y-3"><p className="text-zinc-400">Record your own practice results. These are self-reported scores, not an automatically graded quiz. Mastery requires 3/3, confidence 4–5, and “Understood”.</p>
 <form className="flex flex-wrap items-end gap-3" onSubmit={async e=>{e.preventDefault();if(!topicId)return;setBusy(true);setError("");setSaved("");try{const id=await ensureSession();const result=await api.assess(id,topicId,mcq,check,verdict);setSaved(`Saved: ${result.mastery_status.replaceAll("_"," ").toLowerCase()}`);await refresh();}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>
 <label>Practice score<select aria-label="Practice score" className="block mt-1 bg-zinc-950 p-2 rounded border border-zinc-700" value={mcq} onChange={e=>setMcq(Number(e.target.value))}>{[0,1,2,3].map(n=><option key={n} value={n}>{n}/3</option>)}</select></label>
 <label>Confidence<select aria-label="Confidence" className="block mt-1 bg-zinc-950 p-2 rounded border border-zinc-700" value={check} onChange={e=>setCheck(Number(e.target.value))}>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}/5</option>)}</select></label>
 <label>Understanding<select aria-label="Understanding" className="block mt-1 bg-zinc-950 p-2 rounded border border-zinc-700" value={verdict} onChange={e=>setVerdict(e.target.value)}><option value="PARTIAL">Partially understood</option><option value="UNDERSTOOD">Understood</option><option value="CONFUSED">Confused</option></select></label>
 <button disabled={disabled||busy||!topicId} className="p-2 rounded bg-orange-500 text-white disabled:opacity-40">{busy?"Saving…":"Save self-assessment"}</button>
 </form>
 {saved&&<p role="status" className="text-emerald-400">{saved}</p>}{error&&<p role="alert" className="text-red-400">{error}</p>}
 {recommendation?.topic&&<button className="text-orange-300 underline text-left" onClick={()=>onSelectTopic(recommendation.recommended_topic_id!)}>Next: {recommendation.topic.topic_name} — {recommendation.recommendation_reason}</button>}
 </div></details>;
}
