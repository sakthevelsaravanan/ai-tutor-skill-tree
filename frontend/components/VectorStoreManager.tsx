"use client";
import {useEffect,useState} from "react";
import {Subject,VectorChunk,VectorSearchResult} from "@/lib/types";
import {api} from "@/lib/api";
import {Search,RefreshCw,ChevronLeft,ChevronRight} from "lucide-react";

export function VectorStoreManager({subject}:{subject?:Subject}) {
 const [chunks,setChunks]=useState<VectorChunk[]>([]);const [total,setTotal]=useState(0);
 const [page,setPage]=useState(0);const [query,setQuery]=useState("");const [results,setResults]=useState<VectorSearchResult[]|null>(null);
 const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 const size=20;
 useEffect(()=>{setPage(0);setQuery("");setResults(null);},[subject?.subject_id]);
 useEffect(()=>{let alive=true;if(!subject)return;setBusy(true);setError("");
 Promise.all([api.getChunks(subject.subject_key,page*size,size),api.getCollectionStats(subject.subject_key)])
 .then(([rows,stats])=>{if(alive){setChunks(rows);setTotal(stats.total_chunks);}})
 .catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setBusy(false);});return()=>{alive=false;};
 },[subject?.subject_key,page]);
 if(!subject)return <p>Select a course from Courses to view its knowledge base.</p>;
 const items=results??chunks;
 return <section className="space-y-4 min-w-0">
  <div className="flex flex-wrap justify-between gap-3 items-end"><div><p className="text-xs text-orange-400 mb-1">Knowledge base</p><h1 className="text-xl font-semibold">{subject.subject_name}</h1><p className="text-sm text-zinc-400 mt-1">Search and inspect the passages your tutor uses.</p></div><span className="text-sm text-zinc-400">{total.toLocaleString()} passages indexed</span></div>
  <form className="flex flex-wrap gap-2" onSubmit={async e=>{e.preventDefault();if(!query.trim())return;setBusy(true);setError("");try{setResults((await api.searchVectors(subject.subject_key,query,6)).results);}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>
   <input aria-label="Search course material" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search your course material..." className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"/>
   <button disabled={busy||!query.trim()} className="rounded-lg bg-orange-500 px-4 py-2 text-sm disabled:opacity-40 flex gap-2 items-center">{busy?<RefreshCw size={16} className="animate-spin"/>:<Search size={16}/>}Search</button>
   {results!==null&&<button type="button" onClick={()=>{setResults(null);setQuery("");}} className="border border-zinc-700 rounded-lg px-3 text-sm">Browse all</button>}
  </form>
  {error&&<p role="alert" className="text-red-400 text-sm">{error}</p>}
  <div className="flex items-center justify-between gap-2 text-xs text-zinc-400"><span>{results!==null?`${results.length} search results`:`Passages ${total?page*size+1:0}–${Math.min((page+1)*size,total)} of ${total}`}</span>{results===null&&<div className="flex items-center gap-2"><button aria-label="Previous passages" disabled={busy||page===0} onClick={()=>setPage(p=>p-1)} className="p-2 border border-zinc-700 rounded disabled:opacity-30"><ChevronLeft size={16}/></button><span>Page {page+1} of {Math.max(1,Math.ceil(total/size))}</span><button aria-label="Next passages" disabled={busy||(page+1)*size>=total} onClick={()=>setPage(p=>p+1)} className="p-2 border border-zinc-700 rounded disabled:opacity-30"><ChevronRight size={16}/></button></div>}</div>
  <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 items-start">
   {items.map(item=><article key={item.id} className="min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 space-y-3"><div className="flex justify-between gap-3 text-xs text-zinc-500"><span className="break-words">{item.metadata?.file_name||'Course notes'}</span><span className="shrink-0">Page {item.metadata?.page_number||'—'}</span></div>{item.metadata?.chapter&&<h2 className="text-sm font-medium text-orange-300">{item.metadata.chapter}</h2>}<p className="text-sm leading-relaxed text-zinc-300 whitespace-pre-line break-words line-clamp-4">{item.document}</p><details className="text-xs text-zinc-400"><summary className="cursor-pointer">Read full passage</summary><p className="mt-2 text-sm whitespace-pre-line break-words">{item.document}</p></details></article>)}
  </div>
  {!busy&&!items.length&&<p className="text-sm text-zinc-400">{results?'No matching passages. Try a different search.':'No passages indexed yet.'}</p>}
 </section>;
}
