import chromadb
from backend.vector_service import vector_service

SAMPLE_DATA = {
    "dsa": [
        {
            "id": "dsa_tb_clrs_p12_c0",
            "text": "Arrays store elements in contiguous memory locations, allowing O(1) random access via pointer arithmetic: address = base_address + index * element_size. This memory contiguity maximizes CPU L1/L2 cache line utilization compared to linked nodes.",
            "meta": {"subject": "dsa", "chapter": "Primitives", "topic_id": 101, "source": "CLRS 4th Ed", "file_name": "CLRS_Algorithms.pdf"}
        },
        {
            "id": "dsa_tb_clrs_p45_c0",
            "text": "A Binary Search Tree (BST) is an organized binary tree where the key in each node must be strictly greater than all keys in its left subtree, and less than or equal to all keys in its right subtree. Inorder traversal yields sorted order. Search, insertion, and deletion operate in O(h) where h is the tree height.",
            "meta": {"subject": "dsa", "chapter": "Trees", "topic_id": 105, "source": "CLRS 4th Ed", "file_name": "CLRS_Algorithms.pdf"}
        },
        {
            "id": "dsa_tb_clrs_p78_c1",
            "text": "AVL trees are self-balancing binary search trees where the balance factor (height(left) - height(right)) of any node is strictly restricted to {-1, 0, +1}. When an insertion or deletion violates this invariant (|BF| >= 2), balance is restored via single (LL, RR) or double (LR, RL) rotations in O(1) time per rotation, guaranteeing O(log N) worst-case search.",
            "meta": {"subject": "dsa", "chapter": "Balanced Trees", "topic_id": 106, "source": "CLRS 4th Ed", "file_name": "CLRS_Algorithms.pdf"}
        },
        {
            "id": "dsa_tb_clrs_p112_c0",
            "text": "Dynamic programming solves optimization problems by breaking them into overlapping subproblems with optimal substructure. Memoization stores top-down recursive results in a hash table or array, while bottom-up tabulation builds solutions iteratively from base cases.",
            "meta": {"subject": "dsa", "chapter": "Dynamic Programming", "topic_id": 109, "source": "CLRS 4th Ed", "file_name": "CLRS_Algorithms.pdf"}
        },
        {
            "id": "dsa_tb_clrs_p145_c0",
            "text": "Dijkstra's algorithm finds single-source shortest paths in weighted directed graphs with non-negative edge weights. Using a min-priority queue (min-heap), it iteratively extracts the vertex u with minimum distance estimate and relaxes all incident edges (u, v) in O((V + E) log V) time.",
            "meta": {"subject": "dsa", "chapter": "Graph Algorithms", "topic_id": 110, "source": "CLRS 4th Ed", "file_name": "CLRS_Algorithms.pdf"}
        }
    ],
    "dvlsi": [
        {
            "id": "dvlsi_tb_weste_p23_c0",
            "text": "The metal-oxide-semiconductor field-effect transistor (MOSFET) operates in three primary physical regions: cutoff (Vgs < Vt), triode/linear (Vds < Vgs - Vt), and saturation (Vds >= Vgs - Vt). In saturation, channel pinch-off occurs at the drain end, and current Ids saturates as a quadratic function of overdrive voltage (Vgs - Vt)^2.",
            "meta": {"subject": "dvlsi", "chapter": "MOS Transistor", "topic_id": 201, "source": "Weste & Harris", "file_name": "CMOS_VLSI_Design.pdf"}
        },
        {
            "id": "dvlsi_tb_weste_p45_c0",
            "text": "The CMOS inverter Voltage Transfer Characteristic (VTC) consists of five operational regions (A through E). The switching threshold Vm is defined where Vin = Vout. Symmetric switching requires matched current drivability: beta_n = beta_p, requiring PMOS channel width Wp to be approximately 2 to 3 times Wn due to lower hole mobility.",
            "meta": {"subject": "dvlsi", "chapter": "CMOS Inverter", "topic_id": 202, "source": "Weste & Harris", "file_name": "CMOS_VLSI_Design.pdf"}
        },
        {
            "id": "dvlsi_tb_weste_p89_c0",
            "text": "Static timing analysis evaluates flip-flop timing constraints. Setup constraint requires data to be stable before the clock edge: Tclk >= Tcq + Tcomb + Tsetup - Tskew. Hold constraint mandates data stability after the clock edge to prevent race-through: Tcq + Tcomb >= Thold + Tskew.",
            "meta": {"subject": "dvlsi", "chapter": "Sequential Timing", "topic_id": 206, "source": "Weste & Harris", "file_name": "CMOS_VLSI_Design.pdf"}
        }
    ],
    "cs": [
        {
            "id": "cs_tb_patterson_p54_c0",
            "text": "A classical RISC datapath divides execution into five pipeline stages: Instruction Fetch (IF), Instruction Decode / Register Fetch (ID), Execute / Address Calculation (EX), Memory Access (MEM), and Write Back (WB). Pipeline hazards are classified as structural, data (RAW, WAR, WAW), and control (branches).",
            "meta": {"subject": "cs", "chapter": "Pipelining", "topic_id": 304, "source": "Patterson & Hennessy", "file_name": "Computer_Organization.pdf"}
        },
        {
            "id": "cs_tb_patterson_p88_c0",
            "text": "Cache memory exploits spatial and temporal locality. Address mapping breaks 32-bit addresses into Tag, Set Index, and Block Offset fields. Direct-mapped caches map each block to one set, while N-way set associative caches allow placement in any of N lines per set, reducing conflict misses.",
            "meta": {"subject": "cs", "chapter": "Memory Hierarchy", "topic_id": 305, "source": "Patterson & Hennessy", "file_name": "Computer_Organization.pdf"}
        }
    ],
    "networks": [
        {
            "id": "net_tb_kurose_p32_c0",
            "text": "The Internet protocol stack comprises five layers: Application (HTTP, DNS), Transport (TCP, UDP), Network (IP, ICMP), Link (Ethernet, Wi-Fi), and Physical. Encapsulation wraps application messages in transport segments, network datagrams, and link frames as they traverse down the stack.",
            "meta": {"subject": "networks", "chapter": "Layered Architecture", "topic_id": 401, "source": "Kurose & Ross", "file_name": "Computer_Networking_TopDown.pdf"}
        },
        {
            "id": "net_tb_kurose_p65_c0",
            "text": "Transmission Control Protocol (TCP) is a connection-oriented, reliable byte-stream protocol. Connection establishment requires a 3-way handshake: Client sends SYN with initial sequence number ISN_c; Server responds with SYN-ACK acknowledging ISN_c + 1 with its own ISN_s; Client replies with ACK acknowledging ISN_s + 1. This synchronizes sequence numbers in both directions before payload transmission.",
            "meta": {"subject": "networks", "chapter": "Transport Layer", "topic_id": 404, "source": "Kurose & Ross", "file_name": "Computer_Networking_TopDown.pdf"}
        },
        {
            "id": "net_tb_kurose_p88_c0",
            "text": "TCP sliding window flow control prevents the sender from overflowing the receiver buffer. The receiver advertises a receive window (RcvWindow) in every TCP header. The sender restricts unacknowledged in-flight bytes: LastByteSent - LastByteAcked <= RcvWindow.",
            "meta": {"subject": "networks", "chapter": "Flow Control", "topic_id": 404, "source": "Kurose & Ross", "file_name": "Computer_Networking_TopDown.pdf"}
        },
        {
            "id": "net_tb_kurose_p115_c0",
            "text": "TCP congestion control operates via Additive Increase Multiplicative Decrease (AIMD). During Slow Start, congestion window (cwnd) doubles every RTT until ssthresh. In Congestion Avoidance, cwnd increases by 1 MSS per RTT. Upon triple duplicate ACKs (Fast Retransmit), cwnd is halved and ssthresh is set to cwnd/2.",
            "meta": {"subject": "networks", "chapter": "Congestion Control", "topic_id": 406, "source": "Kurose & Ross", "file_name": "Computer_Networking_TopDown.pdf"}
        },
        {
            "id": "net_tb_kurose_p140_c0",
            "text": "Link-state routing protocols like OSPF use Dijkstra's algorithm to compute minimum cost paths. Every router broadcasts link states using Link State Advertisements (LSAs), giving every node an identical topological map of the entire autonomous system before computing shortest paths.",
            "meta": {"subject": "networks", "chapter": "Routing Protocols", "topic_id": 405, "source": "Kurose & Ross", "file_name": "Computer_Networking_TopDown.pdf"}
        }
    ]
}

def seed_chroma():
    print("Seeding sample textbook vectors into ChromaDB...")
    for subject, chunks in SAMPLE_DATA.items():
        # Clear existing to prevent duplicate IDs on re-seed
        col = vector_service.get_or_create_collection(subject)
        existing_ids = [c["id"] for c in chunks]
        try:
            col.delete(ids=existing_ids)
        except Exception:
            pass

        docs = [c["text"] for c in chunks]
        metas = [c["meta"] for c in chunks]
        ids = [c["id"] for c in chunks]
        vector_service.add_chunks(subject, docs, metas, ids)
        stats = vector_service.get_stats(subject)
        print(f"Collection 'chroma_{subject}': {stats['total_chunks']} chunks indexed.")
    print("Vector seeding complete!")

if __name__ == "__main__":
    seed_chroma()
