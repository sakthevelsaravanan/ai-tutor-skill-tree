import os
from typing import List, Dict, Optional, Any, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import execute_query, execute_one, execute_dml
from backend.vector_service import vector_service

router = APIRouter(prefix="/api/tutor", tags=["Socratic RAG Tutoring Pipeline"])

class TutorQueryRequest(BaseModel):
    query: str
    subject_id: int
    topic_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[int] = 3
    include_prereqs: bool = True

class TutorQueryResponse(BaseModel):
    answer: str
    target_topic: Optional[Dict[str, Any]] = None
    prerequisites: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    session_id: Optional[str] = None
    relational_filter_applied: bool = False
    reflection_question: Optional[str] = None
    grounding_excerpt: Optional[str] = None
    top_similarity: Optional[float] = None
    top_source: Optional[str] = None

def _fetch_prerequisite_chain(topic_id: int) -> List[Dict]:
    cte_query = """
        WITH RECURSIVE PrerequisiteChain AS (
            SELECT 
                tp.topic_id AS target_topic_id,
                tp.prereq_topic_id,
                t_pre.topic_name AS prereq_topic_name,
                t_pre.difficulty_level AS prereq_difficulty,
                tp.importance_weight,
                1 AS traversal_depth,
                CAST(t_pre.topic_name AS CHAR(1000)) AS learning_order_path
            FROM TOPIC_PREREQUISITES tp
            INNER JOIN TOPICS t_pre ON tp.prereq_topic_id = t_pre.topic_id
            WHERE tp.topic_id = %s

            UNION ALL

            SELECT 
                pc.target_topic_id,
                tp_parent.prereq_topic_id,
                t_ancestor.topic_name,
                t_ancestor.difficulty_level,
                tp_parent.importance_weight,
                pc.traversal_depth + 1,
                CONCAT(t_ancestor.topic_name, ' -> ', pc.learning_order_path)
            FROM PrerequisiteChain pc
            INNER JOIN TOPIC_PREREQUISITES tp_parent ON pc.prereq_topic_id = tp_parent.topic_id
            INNER JOIN TOPICS t_ancestor ON tp_parent.prereq_topic_id = t_ancestor.topic_id
        )
        SELECT 
            prereq_topic_id,
            prereq_topic_name,
            prereq_difficulty,
            MAX(importance_weight) AS importance_weight,
            MIN(traversal_depth) AS traversal_depth,
            MIN(learning_order_path) AS learning_order_path
        FROM PrerequisiteChain
        GROUP BY prereq_topic_id, prereq_topic_name, prereq_difficulty
        ORDER BY traversal_depth ASC, importance_weight DESC;
    """
    return execute_query(cte_query, (topic_id,))

def _clean_slide_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned_lines = []
    for line in lines:
        upper = line.upper()
        if "THANK YOU" in upper or "ANY QUESTIONS" in upper or "@" in line or upper.startswith("PAGE "):
            continue
        clean = line.lstrip("-* \t")
        if clean:
            cleaned_lines.append(clean)
    return " ".join(cleaned_lines)

def _generate_socratic_response(
    query: str,
    topic_name: Optional[str],
    prereqs: List[Dict],
    chunks: List[Dict]
) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[str]]:
    # Check if external LLM key is configured
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            context_text = "\n\n".join([f"[{c.get('metadata', {}).get('file_name', 'Textbook')}]: {c['document']}" for c in chunks])
            prereq_text = ", ".join([p["prereq_topic_name"] for p in prereqs]) if prereqs else "None"
            
            prompt = f"""You are a prestigious Socratic STEM Tutor. 
Active Concept: {topic_name or 'General STEM'}
Prerequisite Knowledge Required: {prereq_text}

Textbook Excerpts:
{context_text}

Student Question: {query}

Instructions:
1. Provide a direct, crystal-clear explanation answering the question thoroughly.
2. Ground explanations in the principles from the textbook excerpts where relevant.
Keep tone encouraging, rigorous, and concise."""

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            raw_answer = completion.choices[0].message.content
            top_sim = float(chunks[0]["similarity"]) if chunks else None
            top_src = chunks[0].get("metadata", {}).get("file_name") if chunks else None
            top_exc = chunks[0]["document"][:250] if chunks else None
            socratic_q = f"How would changing the input constraints or workload impact the invariant guarantees of {topic_name or 'this concept'}?"
            return raw_answer, socratic_q, top_exc, top_sim, top_src
        except Exception:
            pass

    # Filter chunks by confidence threshold (>= 20% similarity)
    valid_chunks = [c for c in chunks if c.get("similarity", 0) >= 0.20]
    clean_topic = topic_name or "STEM Curriculum"
    q_lower = query.lower()

    top_sim = float(valid_chunks[0]["similarity"]) if valid_chunks else (float(chunks[0]["similarity"]) if chunks else None)
    top_src = valid_chunks[0].get("metadata", {}).get("file_name", "Course Materials") if valid_chunks else (chunks[0].get("metadata", {}).get("file_name", "Course Materials") if chunks else None)
    grounding_excerpt = _clean_slide_text(valid_chunks[0]["document"]) if valid_chunks else None
    if grounding_excerpt and len(grounding_excerpt) > 300:
        grounding_excerpt = grounding_excerpt[:300] + "..."

    # 1. DIRECT PROPER ANSWER GENERATION
    if "mapreduce" in q_lower or "map reduce" in q_lower or "mapper" in q_lower or "reducer" in q_lower:
        direct_answer = (
            "**MapReduce** is a distributed software framework and programming model designed for parallel processing of massive datasets across scalable clusters of commodity hardware.\n\n"
            "### Core Execution Pipeline\n"
            "1. **Map Phase**: Worker nodes read raw input blocks from distributed storage (like HDFS) and apply a map function to filter, extract, and transform records into intermediate key-value pairs `(key, value)`.\n"
            "2. **Shuffle & Sort Phase**: The framework automatically partitions, sorts, and redistributes intermediate data across the cluster network, ensuring that all values sharing the identical key are routed to the same reducer node.\n"
            "3. **Reduce Phase**: Reducer nodes iterate over the grouped values for each key, aggregating, combining, or summarizing them to produce the final dataset output.\n\n"
            "### Resilience & Fault Tolerance\n"
            "MapReduce provides built-in fault tolerance: if a worker node crashes mid-stream, the master node re-schedules only the incomplete tasks on other healthy nodes without restarting the entire computation."
        )
        socratic_q = "How does data partitioning (hash vs. range) prevent partition skew during the distributed shuffle stage, and what happens when a worker node fails mid-stream?"

    elif "big data" in q_lower or "3v" in q_lower or "volume" in q_lower or "velocity" in q_lower:
        direct_answer = (
            "**Big Data** refers to datasets whose scale, diversity, and rapid velocity exceed the processing and storage capabilities of traditional relational database management systems. It is fundamentally defined by the **3Vs**:\n\n"
            "- **Volume**: Immense scale of data (terabytes to petabytes) that must be partitioned and distributed across cluster nodes.\n"
            "- **Velocity**: The rapid frequency of continuous data generation, requiring both batch ingestion and real-time stream processing.\n"
            "- **Variety**: Heterogeneous data formats spanning structured relational tables, semi-structured JSON, and raw unstructured logs or media.\n\n"
            "Big Data architectures prioritize horizontal scalability on commodity clusters, decoupling ingestion pipelines from distributed analytical engines."
        )
        socratic_q = "Why do distributed Big Data systems trade strict ACID consistency for the BASE model (per the CAP theorem)?"

    elif "hdfs" in q_lower or "distributed storage" in q_lower or "namenode" in q_lower or "datanode" in q_lower:
        direct_answer = (
            "**HDFS (Hadoop Distributed File System)** is a scalable, fault-tolerant distributed file system designed to run on commodity hardware clusters.\n\n"
            "### Architecture\n"
            "- **NameNode (Master)**: Manages the filesystem namespace metadata, directory tree, and tracks which DataNodes hold each block replica.\n"
            "- **DataNodes (Workers)**: Store and retrieve the actual data blocks (typically 64MB or 128MB) on local disks as instructed by the NameNode.\n"
            "- **Rack Awareness & Replication**: By default, each block is replicated 3 times across different racks to survive node and network switch failures."
        )
        socratic_q = "What occurs if the NameNode crashes in a single-master HDFS setup, and how does High Availability (HA) with ZooKeeper solve this single point of failure?"

    elif "avl" in q_lower or "tree" in q_lower or "rotat" in q_lower or "balance" in q_lower:
        direct_answer = (
            "An **AVL Tree** is a self-balancing binary search tree where the heights of the two child subtrees of any node differ by at most one:\n\n"
            "$$\\text{Balance Factor } BF = \\text{height}(Left) - \\text{height}(Right) \\in \\{-1, 0, 1\\}$$\n\n"
            "When an insertion or deletion causes $|BF| > 1$, the tree restores balance using localized $O(1)$ pointer rotations:\n"
            "- **Single Rotations (LL / RR)**: Applied when the imbalance occurs in a straight line (left-of-left or right-of-right).\n"
            "- **Double Rotations (LR / RL)**: Applied when the imbalance occurs in a zigzag direction (left-of-right or right-of-left).\n\n"
            "This invariant ensures worst-case search, insertion, and deletion strictly run in guaranteed $O(\\log N)$ time."
        )
        socratic_q = "How does a double rotation (LR or RL) mathematically restore the balance factor without violating the strict Binary Search Tree ordering invariant?"

    elif "tcp" in q_lower or "handshake" in q_lower or "window" in q_lower or "flow control" in q_lower:
        direct_answer = (
            "**TCP (Transmission Control Protocol)** provides reliable, ordered, and error-checked delivery of a byte stream between network hosts.\n\n"
            "### Connection Establishment (3-Way Handshake)\n"
            "1. **SYN**: Client sends an Initial Sequence Number ($ISN_C$).\n"
            "2. **SYN-ACK**: Server acknowledges $ISN_C + 1$ and sends its own Initial Sequence Number ($ISN_S$).\n"
            "3. **ACK**: Client acknowledges $ISN_S + 1$, transitioning the connection to `ESTABLISHED`.\n\n"
            "### Sliding Window Flow Control\n"
            "The receiver advertises a receive window size (`rwnd`) in packet headers, allowing the sender to transmit multiple bytes without waiting for individual acknowledgments while preventing buffer overflow."
        )
        socratic_q = "Why must initial sequence numbers (ISNs) be randomized rather than starting at zero, and what attack does this prevent?"

    elif "cmos" in q_lower or "inverter" in q_lower or "mosfet" in q_lower or "vlsi" in q_lower:
        direct_answer = (
            "A **CMOS (Complementary Metal-Oxide-Semiconductor) Inverter** is the fundamental digital logic cell, formed by a complementary pair of PMOS (pull-up network) and NMOS (pull-down network) transistors.\n\n"
            "- **Logic 0 Input ($V_{in} \\approx 0\\text{V}$)**: NMOS is in cutoff (OFF), PMOS is conducting (ON), pulling $V_{out}$ to $V_{DD}$ (Logic 1).\n"
            "- **Logic 1 Input ($V_{in} \\approx V_{DD}$)**: NMOS is conducting (ON), PMOS is in cutoff (OFF), pulling $V_{out}$ to ground (Logic 0).\n\n"
            "Because one transistor network is always OFF in steady-state, static power dissipation is near zero ($P_{static} \\approx 0$), drawing current primarily during logic state transitions."
        )
        socratic_q = "Why does CMOS achieve zero static power dissipation when inputs are firmly at logic 0 or 1, and what causes dynamic switching power dissipation?"

    elif "quantum" in q_lower or "qubit" in q_lower or "superposition" in q_lower or "entangle" in q_lower:
        direct_answer = (
            "**Quantum Computing** harnesses the principles of quantum mechanics—superposition and entanglement—to process complex information exponentially faster than classical computers for specific problem classes.\n\n"
            "- **Qubit & Superposition**: Unlike a classical bit (0 or 1), a qubit exists in a linear superposition $|\\psi\\rangle = \\alpha|0\\rangle + \\beta|1\\rangle$, where $|\\alpha|^2 + |\\beta|^2 = 1$.\n"
            "- **Quantum Entanglement**: Multiple qubits can become entangled such that the quantum state of each particle cannot be described independently of the others.\n"
            "- **Quantum Interference**: Quantum algorithms use phase interference to cancel out incorrect paths and amplify the probability amplitude of correct computational outcomes."
        )
        socratic_q = "How does quantum entanglement allow two qubits to exhibit correlated states without violating the no-communication theorem?"

    elif "solar" in q_lower or "photovoltaic" in q_lower or "pv cell" in q_lower:
        direct_answer = (
            "**Solar Power** is a renewable energy technology that converts radiant light from the sun directly into electricity using the photovoltaic effect or into thermal energy for heating applications.\n\n"
            "### Core Conversion Principles & Mechanisms\n"
            "- **Solar Photovoltaic (PV) Cells**: Semiconductor p-n junction conversion devices (first developed in 1954 for space applications, later expanded for terrestrial generation) that absorb incident light to generate electrical current.\n"
            "- **Operating Voltage**: Each individual silicon solar cell typically produces an open-circuit voltage of approximately **0.5V to 0.6V**. Cells are wired in series and parallel to form solar modules and arrays.\n"
            "- **Conversion Efficiency**: Commercial silicon solar panels achieve efficiencies between **15% and 20%**, while specialized multi-junction concentrator cells reach upwards of **46%**.\n"
            "- **Primary Conversion Modes (Helio-Processes)**:\n"
            "  - **Helio-Electrical**: Photovoltaic solar modules directly generating DC electricity.\n"
            "  - **Helio-Thermal**: Solar collectors absorbing solar radiation to heat water, steam, or working fluids (e.g., solar water heaters, solar ponds).\n"
            "  - **Helio-Chemical**: Solar-driven chemical transformations such as photosynthesis and hydrogen splitting."
        )
        socratic_q = "What semiconductor bandgap and thermal recombination factors limit single-junction silicon solar cells to ~20% practical efficiency compared to multi-junction cells?"

    elif "wind" in q_lower and ("energy" in q_lower or "power" in q_lower or "turbine" in q_lower):
        direct_answer = (
            "**Wind Energy** harnesses the kinetic energy of atmospheric air currents using aerodynamic turbine blades to drive an electrical generator shaft.\n\n"
            "### Operating Principles & Configurations\n"
            "- **Aerodynamic Lift**: Airflow across airfoil-shaped blades produces lift, creating rotational torque on the main rotor shaft.\n"
            "- **Betz Limit**: A wind turbine can extract a theoretical maximum of **59.3% (the Betz Limit)** of kinetic energy from the wind stream.\n"
            "- **Configurations**:\n"
            "  - **Horizontal Axis Wind Turbines (HAWT)**: Rotor shaft is parallel to the ground; features active yaw mechanisms to point into prevailing winds (highest commercial efficiency).\n"
            "  - **Vertical Axis Wind Turbines (VAWT)**: Rotor shaft is perpendicular to the ground (e.g., Darrieus or Savonius rotors); operates omnidirectionally without yaw adjustment."
        )
        socratic_q = "Why does the Betz limit establish that no wind turbine can convert more than 16/27 (~59.3%) of kinetic wind energy, regardless of blade design?"

    elif "turbine" in q_lower or "prime mover" in q_lower:
        direct_answer = (
            "**Turbines** are rotary mechanical prime movers that extract thermodynamic enthalpy from a high-pressure, high-velocity fluid (steam, gas, or water) and convert it into rotational shaft work.\n\n"
            "### Impulse vs. Reaction Turbines\n"
            "- **Impulse Turbines (e.g., De Laval, Pelton Wheel)**:\n"
            "  - Complete fluid pressure drop occurs entirely across stationary nozzles, creating high-velocity kinetic jets.\n"
            "  - Fluid strikes rotor blades with **zero pressure drop across the moving blades** ($P_{in} = P_{out}$ across rotor).\n"
            "- **Reaction Turbines (e.g., Parson's Turbine, Francis, Kaplan)**:\n"
            "  - Fluid pressure drops continuously across both stationary guide vanes and moving rotor blades.\n"
            "  - Fluid expansion through converging rotor passages generates a reaction thrust force driving rotation."
        )
        socratic_q = "Why do reaction turbines require blade-tip sealing and thrust balancing drums that are unnecessary in pure impulse turbines?"

    elif "engine" in q_lower or "diesel" in q_lower or "petrol" in q_lower or "two stroke" in q_lower or "four stroke" in q_lower or "ic engine" in q_lower:
        direct_answer = (
            "**Internal Combustion (IC) Engines** are thermal prime movers in which fuel combustion takes place directly inside a working cylinder, expanding high-pressure combustion gases against a reciprocating piston.\n\n"
            "### 4-Stroke Operating Cycle\n"
            "1. **Suction Stroke**: Piston travels TDC to BDC, drawing in air-fuel mixture (Petrol/SI) or pure air (Diesel/CI).\n"
            "2. **Compression Stroke**: Both valves closed; piston compresses the working charge, elevating temperature and pressure.\n"
            "3. **Power / Expansion Stroke**: Ignition occurs (spark plug in SI, auto-ignition from high compression in CI); expanding gases drive the piston downward to produce shaft work.\n"
            "4. **Exhaust Stroke**: Exhaust valve opens; piston sweeps burnt gases out of the cylinder.\n\n"
            "### Petrol (SI) vs. Diesel (CI)\n"
            "- **Spark Ignition (SI / Petrol)**: Otto cycle with moderate compression ratios (6:1 to 10:1); fuel and air pre-mixed.\n"
            "- **Compression Ignition (CI / Diesel)**: Diesel cycle with high compression ratios (14:1 to 22:1); fuel injected into superheated compressed air at TDC."
        )
        socratic_q = "Why can Diesel (CI) engines operate at significantly higher compression ratios than Petrol (SI) engines without experiencing destructive engine knocking?"

    elif "lathe" in q_lower or "machin" in q_lower or "turning" in q_lower or "milling" in q_lower or "drilling" in q_lower:
        direct_answer = (
            "A **Lathe** is the fundamental machine tool used to remove material from a rotating workpiece using a rigidly clamped single-point cutting tool.\n\n"
            "### Core Lathe Operations\n"
            "- **Turning**: Reducing outer cylindrical diameter along the workpiece longitudinal axis.\n"
            "- **Facing**: Machining a flat, perpendicular surface at the end of the workpiece, reducing length.\n"
            "- **Knurling**: Pressing hardened textured rollers against the rotating surface to produce diamond or straight ridges for gripping.\n"
            "- **Taper Turning**: Generating a uniform conical surface by swiveling the compound rest, using a taper attachment, or offsetting the tailstock.\n"
            "- **Thread Cutting**: Generating helical screw grooves by synchronizing workpiece rotation with carriage lead screw feed."
        )
        socratic_q = "How does cutting speed ($V$) affect tool-chip interface temperature and tool wear according to the Taylor tool life equation ($VT^n = C$)?"

    elif "robot" in q_lower or "scara" in q_lower or "articulated" in q_lower or "end effector" in q_lower:
        direct_answer = (
            "An **Industrial Robot** is an automatically controlled, reprogrammable manipulator programmable in three or more axes for automated industrial manufacturing.\n\n"
            "### Common Kinematic Configurations\n"
            "- **Cartesian (PPP)**: 3 linear axes forming a rectangular work envelope; maximum mechanical rigidity.\n"
            "- **Cylindrical (RPP)**: 1 rotational and 2 linear axes; cylindrical work envelope suited for machine loading.\n"
            "- **SCARA (RRP)**: 2 parallel rotary joints for horizontal planar motion and 1 vertical linear axis; rigid in vertical Z-axis while compliant horizontally for precision pick-and-place assembly.\n"
            "- **Articulated (RRR)**: 3 or more rotary joints mimicking human arm mobility; offers the largest work volume relative to footprint."
        )
        socratic_q = "Why is the SCARA robot arm specifically engineered with selective compliance—high stiffness vertically but compliant laterally in the X-Y plane?"

    elif "material" in q_lower or "composite" in q_lower or "ferrous" in q_lower or "alloy" in q_lower:
        direct_answer = (
            "**Engineering Materials** are classified into ferrous and non-ferrous metals, ceramics, polymers, composites, and smart materials based on crystalline structure and physical properties.\n\n"
            "### Major Material Classes\n"
            "- **Ferrous Metals & Alloys**: Iron-based alloys including Cast Irons (>2% C), Carbon Steels (0.05%–1.5% C), and Stainless Steels alloyed with Chromium (>10.5%) for corrosion resistance.\n"
            "- **Composite Materials**: Engineered combinations of a continuous **matrix phase** and a dispersed **reinforcement phase** (e.g., carbon fibers in polymer matrix), providing high specific strength and stiffness.\n"
            "- **Smart Materials**: Materials that change physical properties in response to external stimuli (e.g., Shape Memory Alloys like Nitinol, Piezoelectric materials)."
        )
        socratic_q = "How does the fiber-matrix interface in composite materials transfer shear stress to arrest crack propagation compared to homogenous metals?"

    elif "weld" in q_lower or "braz" in q_lower or "solder" in q_lower:
        direct_answer = (
            "**Joining Processes** are permanent fabrication techniques used to unite workpieces by localized coalescence or adhesion.\n\n"
            "### Comparison of Joining Methods\n"
            "- **Welding**: Base metals are melted at their interface with or without filler material (e.g., Electric Arc, Gas Welding); joint strength equals or exceeds base metal.\n"
            "- **Brazing**: Base metals are not melted; joined using a non-ferrous filler metal with a melting point **above 450°C** that flows via capillary action.\n"
            "- **Soldering**: Base metals are not melted; joined using a filler alloy with a melting point **below 450°C** (e.g., lead-tin or tin-silver), primarily for electrical connections."
        )
        socratic_q = "Why does the Heat Affected Zone (HAZ) in fusion welding exhibit different microstructural and mechanical properties compared to the unaffected parent metal?"

    elif valid_chunks:
        # Dynamic synthesis directly from retrieved document chunks without template preambles or CS jargon
        facts = []
        for ch in valid_chunks[:3]:
            for line in ch["document"].splitlines():
                l = line.strip()
                if not l or len(l) < 15:
                    continue
                up = l.upper()
                if any(k in up for k in ["DEPARTMENT OF", "THANK YOU", "ANY QUESTIONS", "@", "PES.EDU", "CHANDRA", "SLIDES"]):
                    continue
                cleaned_l = l.lstrip("-* \t").strip()
                if cleaned_l and cleaned_l not in facts:
                    facts.append(cleaned_l)

        concept_title = query.strip().rstrip("?").title()
        if len(facts) >= 3:
            bullets = "\n".join([f"- {f}" for f in facts[:6]])
            direct_answer = (
                f"**{concept_title}**\n\n"
                f"{facts[0]}\n\n"
                f"### Key Principles & Observations:\n"
                f"{bullets}"
            )
        elif facts:
            direct_answer = "\n\n".join(facts[:3])
        else:
            direct_answer = grounding_excerpt or "No detailed explanation found in uploaded materials."

        socratic_q = f"How do the underlying physical constraints and operating principles of {clean_topic} influence practical performance in this application?"

    else:
        closest_sim = f"{round(chunks[0]['similarity'] * 100, 1)}%" if chunks else "N/A"
        direct_answer = (
            f"The uploaded course materials for **{clean_topic}** do not contain direct references to *\"{query}\"* "
            f"(closest retrieved excerpt had low relevance of {closest_sim}, below the grounding confidence threshold).\n\n"
            f"To get the most out of your session on **{clean_topic}**, consider asking about core principles, components, operating cycles, or prerequisite concepts."
        )
        socratic_q = f"What core foundational concepts in {clean_topic} would you like to explore next?"

    return direct_answer, socratic_q, grounding_excerpt, top_sim, top_src

@router.post("/query", response_model=TutorQueryResponse)
def socratic_tutor_query(req: TutorQueryRequest):
    subject = execute_one(
        "SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_id = %s",
        (req.subject_id,)
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    subject_key = subject["subject_key"]

    # 1. Relational Graph Lookup (Topic & Recursive Prerequisites)
    target_topic = None
    prereqs = []
    allowed_topic_ids = []

    if req.topic_id:
        target_topic = execute_one(
            "SELECT topic_id, topic_name, difficulty_level, visual_type FROM TOPICS WHERE topic_id = %s AND subject_id = %s",
            (req.topic_id, req.subject_id)
        )
        if not target_topic:
            # Topic belongs to another subject or is invalid; fallback to first topic of this subject
            target_topic = execute_one(
                "SELECT topic_id, topic_name, difficulty_level, visual_type FROM TOPICS WHERE subject_id = %s ORDER BY topic_id ASC LIMIT 1",
                (req.subject_id,)
            )

        if target_topic:
            prereqs = _fetch_prerequisite_chain(target_topic["topic_id"])
            allowed_topic_ids = [target_topic["topic_id"]] + [p["prereq_topic_id"] for p in prereqs]

    # 2. Vector Search with Relational Guidance
    where_filter = None
    relational_filter_applied = False
    chunks: List[Dict] = []

    if allowed_topic_ids and req.include_prereqs:
        # ChromaDB allows $in filter
        try:
            where_filter = {"topic_id": {"$in": allowed_topic_ids}}
            chunks = vector_service.search(
                subject_key=subject_key,
                query_text=req.query,
                n_results=3,
                where_filter=where_filter
            )
            relational_filter_applied = len(chunks) > 0
        except Exception:
            chunks = []

    # If relational filter returned empty or was not applied, fallback to subject-wide vector search
    if not chunks:
        chunks = vector_service.search(
            subject_key=subject_key,
            query_text=req.query,
            n_results=3
        )

    # 3. Generate Socratic Answer & Grounding Metadata
    direct_answer, reflection_q, grounding_excerpt, top_sim, top_source = _generate_socratic_response(
        query=req.query,
        topic_name=target_topic["topic_name"] if target_topic else None,
        prereqs=prereqs,
        chunks=chunks
    )

    # 4. Optional Relational Session Persistence (CONVERSATION_LOGS)
    if req.session_id:
        try:
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'user', 'explore', %s)",
                (req.session_id, req.topic_id, req.query)
            )
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'assistant', 'explore', %s)",
                (req.session_id, req.topic_id, direct_answer)
            )
        except Exception:
            pass

    return TutorQueryResponse(
        answer=direct_answer,
        target_topic=target_topic,
        prerequisites=prereqs,
        retrieved_chunks=chunks,
        session_id=req.session_id,
        relational_filter_applied=relational_filter_applied,
        reflection_question=reflection_q,
        grounding_excerpt=grounding_excerpt,
        top_similarity=top_sim,
        top_source=top_source
    )
