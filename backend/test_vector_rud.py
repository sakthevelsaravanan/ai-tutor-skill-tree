from backend.vector_service import vector_service

def test_rud():
    subject = "dsa"
    test_id = "dsa_test_chunk_999"
    test_doc = "B-Trees are self-balancing search trees designed to work well on disks or secondary storage devices."
    test_meta = {"subject": "dsa", "topic_id": 999, "chapter": "Advanced Trees"}

    print("--- 1. CREATE ---")
    vector_service.add_chunks(subject, [test_doc], [test_meta], [test_id])
    print(f"Added chunk '{test_id}'. Total chunks in chroma_{subject}: {vector_service.get_stats(subject)['total_chunks']}")

    print("\n--- 2. READ (Semantic Search) ---")
    matches = vector_service.search(subject, "How do disk storage search trees work?", n_results=1)
    assert len(matches) > 0
    print(f"Top match ID: {matches[0]['id']}")
    print(f"Similarity: {matches[0]['similarity']}")
    print(f"Text: {matches[0]['document'][:80]}...")

    print("\n--- 3. UPDATE ---")
    updated_doc = "B+ Trees store all data records in leaf nodes only, with internal nodes storing search keys."
    vector_service.update_chunk(subject, test_id, updated_doc, {"subject": "dsa", "chapter": "B+ Trees"})
    updated_matches = vector_service.search(subject, "Where are data records stored in a B+ tree?", n_results=1)
    print(f"Updated match text: {updated_matches[0]['document'][:80]}...")
    assert "leaf nodes only" in updated_matches[0]["document"]
    print("Update verified successfully!")

    print("\n--- 4. DELETE ---")
    deleted = vector_service.delete_chunks(subject, ids=[test_id])
    print(f"Deleted {deleted} chunk(s). Remaining in chroma_{subject}: {vector_service.get_stats(subject)['total_chunks']}")
    print("\nAll Vector RUD operations passed successfully!")

if __name__ == "__main__":
    test_rud()
