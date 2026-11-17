import json
import sqlite3

def check_term(paper_id, term):
    with open(f"data/chunks/langchain_recursive/{paper_id}.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        matches = []
        for c in data["chunks"]:
            text = c.get("chunk_text", "") or c.get("content", "")
            if term.lower() in text.lower():
                matches.append((c["chunk_id"], c.get("page_number"), c.get("section"), text[:120].replace("\n", " ")))
        print(f"\n{paper_id} matches for '{term}': {len(matches)}")
        for cid, page, sec, snippet in matches[:3]:
            print(f"   [{cid}] p.{page} sec.{sec}: {snippet}")

def check_facts(paper_id, term):
    conn = sqlite3.connect("data/indexes/fact_store.db")
    c = conn.cursor()
    rows = c.execute(
        "SELECT chunk_id, page_number, section, element_type, substr(content, 1, 100) FROM facts WHERE paper_id = ? AND content LIKE ?",
        (paper_id, f"%{term}%")
    ).fetchall()
    print(f"\nFactStore {paper_id} matches for '{term}': {len(rows)}")
    for r in rows[:3]:
        print(f"   [{r[0]}] p.{r[1]} sec.{r[2]} ({r[3]}): {r[4].replace('\n', ' ')}")
    conn.close()

if __name__ == "__main__":
    check_term("1706.03762v7", "28.4")
    check_facts("1706.03762v7", "28.4")
    check_term("1706.03762v7", "d_model")
    check_term("1706.03762v7", "scaled dot-product")
    check_term("1706.03762v7", "sinusoid")
    check_facts("1706.03762v7", "Table 1")

    check_term("2410.00037v1", "Mimi")
    check_term("2410.00037v1", "Helium")
    check_term("2410.00037v1", "Depth Transformer")
    check_facts("2410.00037v1", "Table 1")
    check_facts("2410.00037v1", "Table 2")

    check_term("2507.07955v2", "Dynamic Chunking")
    check_term("2507.07955v2", "H-Net")
    check_term("2507.07955v2", "SpaceByte")
    check_facts("2507.07955v2", "Table 1")
    check_facts("2507.07955v2", "Table 2")
