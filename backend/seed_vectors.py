from backend.vector_service import vector_service

SAMPLE_DATA = {
    "dsa": [
        {
            "id": "dsa_tb_clrs_p45_c0",
            "text": "A Binary Search Tree (BST) is an organized binary tree where the key in each node must be greater than or equal to any key stored in its left sub-tree, and less than or equal to any key stored in its right sub-tree. Searching takes O(h) where h is the tree height.",
            "meta": {"subject": "dsa", "chapter": "Trees", "topic_id": 105, "source": "CLRS 4th Ed"}
        },
        {
            "id": "dsa_tb_clrs_p78_c1",
            "text": "AVL trees are self-balancing binary search trees where the heights of the two child subtrees of any node differ by at most one. If at any time they differ by more than one, rebalancing is done via tree rotations: Left-Left, Right-Right, Left-Right, or Right-Left.",
            "meta": {"subject": "dsa", "chapter": "Balanced Trees", "topic_id": 106, "source": "CLRS 4th Ed"}
        },
        {
            "id": "dsa_tb_clrs_p112_c0",
            "text": "Dynamic programming applies when subproblems overlap. Memoization is an optimization technique used primarily to speed up computer programs by storing the results of expensive function calls and returning the cached result when the same inputs occur again.",
            "meta": {"subject": "dsa", "chapter": "Dynamic Programming", "topic_id": 109, "source": "CLRS 4th Ed"}
        }
    ],
    "dvlsi": [
        {
            "id": "dvlsi_tb_weste_p23_c0",
            "text": "The metal-oxide-semiconductor field-effect transistor (MOSFET) operates in three primary regions: cutoff (Vgs < Vt), linear or triode (Vds < Vgs - Vt), and saturation (Vds >= Vgs - Vt). In saturation, the channel pinches off and drain current becomes relatively constant.",
            "meta": {"subject": "dvlsi", "chapter": "MOS Transistor", "topic_id": 201, "source": "Weste & Harris"}
        },
        {
            "id": "dvlsi_tb_weste_p89_c0",
            "text": "Static timing analysis evaluates the setup time (Tsetup) and hold time (Thold). Setup constraint dictates that data must be stable before the active clock edge: Tclk >= Tcq + Tcomb + Tsetup - Tskew. Hold constraint dictates data must stay stable after clock edge: Tcq + Tcomb >= Thold + Tskew.",
            "meta": {"subject": "dvlsi", "chapter": "Sequential Timing", "topic_id": 206, "source": "Weste & Harris"}
        }
    ],
    "cs": [
        {
            "id": "cs_tb_patterson_p54_c0",
            "text": "A classical RISC datapath consists of five pipeline stages: Instruction Fetch (IF), Instruction Decode and Register Read (ID), Execution or Address Calculation (EX), Memory Access (MEM), and Write Back (WB). Pipelining improves instruction throughput.",
            "meta": {"subject": "cs", "chapter": "Pipelining", "topic_id": 304, "source": "Patterson & Hennessy"}
        }
    ]
}

def seed_chroma():
    print("Seeding sample textbook vectors into ChromaDB...")
    for subject, chunks in SAMPLE_DATA.items():
        docs = [c["text"] for c in chunks]
        metas = [c["meta"] for c in chunks]
        ids = [c["id"] for c in chunks]
        vector_service.add_chunks(subject, docs, metas, ids)
        stats = vector_service.get_stats(subject)
        print(f"Collection 'chroma_{subject}': {stats['total_chunks']} chunks indexed.")
    print("Vector seeding complete!")

if __name__ == "__main__":
    seed_chroma()
