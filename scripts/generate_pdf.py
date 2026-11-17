import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
import pymupdf

def build_pdf():
    pdf_path = "submission/final_submission.pdf"
    
    # 0.35 inch margins to maximize usable area while keeping printable border
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=26,
        rightMargin=26,
        topMargin=24,
        bottomMargin=24
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#475569'),
        spaceAfter=4
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=4,
        spaceAfter=2,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyCompact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.8,
        leading=8.6,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=2
    )
    
    body_bold = ParagraphStyle(
        'BodyCompactBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    code_style = ParagraphStyle(
        'CodeCompact',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.2,
        leading=7.8,
        textColor=colors.HexColor('#334155'),
        spaceAfter=2
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.8,
        leading=7.2,
        textColor=colors.HexColor('#0F172A')
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold'
    )
    
    table_hdr = ParagraphStyle(
        'TableHdr',
        parent=table_cell,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0F172A')
    )

    story = []
    
    # Header
    story.append(Paragraph("The Relay — Research Assistant: Technical Report", title_style))
    story.append(Paragraph("<b>Candidate:</b> ML Engineering Submission &nbsp;|&nbsp; <b>Model:</b> <font name='Courier'>openai/gpt-oss-120b</font> (Groq LPU Cloud) &nbsp;|&nbsp; <b>Corpus:</b> 3 arXiv Papers (120 pp., 402 chunks)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=3, spaceBefore=0))
    
    # 1. What I built and why
    story.append(Paragraph("1. What I built and why", h1_style))
    story.append(Paragraph(
        "I engineered <b>The Relay</b>, an end-to-end, production-grade research assistant that answers deep technical questions exclusively grounded in three machine learning papers (<i>Attention Is All You Need</i>, <i>Moshi</i>, and <i>Dynamic Chunking</i>). The core pipeline is structured as an 8-node stateful <b>LangGraph</b> workflow that strictly decouples retrieval from generation. Ingestion preserves document geometry and 1-based page numbers via PyMuPDF; chunking applies token-aware recursive splitting (512 tokens, 76 overlap) with Markdown table caption preservation. Retrieval combines ChromaDB dense vectors (<font name='Courier'>all-MiniLM-L6-v2</font>), Rank-BM25 lexical search, and an SQLite FactStore fused via Reciprocal Rank Fusion (<i>k</i>=60). A citation verification node validates bracketed citations (<font name='Courier'>[Title, arXiv:ID, p. X, Section Y]</font>) against retrieved chunks; ungrounded claims trigger a single bounded revision loop or grounded refusal. The most critical architectural decision was placing an <b>asynchronous TrafficManager</b> before model execution, coordinating a FIFO queue, token-bucket rate limiting (RPM/TPM), semaphore concurrency (<i>N</i>=4), and cooperative cancellation to prevent cascade failures under burst load.",
        body_style
    ))
    
    # 2. The real service and my stand-in
    story.append(Paragraph("2. The real service and my stand-in", h1_style))
    story.append(Paragraph(
        "The target service is <font name='Courier'>openai/gpt-oss-120b</font> on Groq's LPU Inference Cloud. Through empirical profiling (20 baseline requests, 10 streaming probes), I characterized runtime performance: median TTFT is <b>852.0 ms</b> (mean 928.1 ms, p95 1360.2 ms), and median total turnaround latency is <b>1031.0 ms</b> (mean 1063.4 ms, p95 1461.6 ms). Response headers revealed strict tier limits: <b>30 RPM</b>, <b>8,000 TPM</b>, and <b>1,000 RPD</b>. I built a local stand-in simulator (<font name='Courier'>simulator/service.py</font>) running FastAPI. To accurately emulate Groq, it samples latency from a calibrated lognormal distribution (&mu;=6.94, &sigma;=0.22, rejection floor 700 ms, matching real p50 of 1033.8 ms and p95 of 1430.7 ms). The simulator faithfully replicates Server-Sent Events (SSE) token chunking (~1.8 ms/token delay), sliding-window token buckets, and HTTP 429 error bodies with <font name='Courier'>retry-after</font> headers. The primary difference is environment determinism: the stand-in runs locally with zero unannounced upstream queue jitter.",
        body_style
    ))
    
    # 3. Results
    story.append(Paragraph("3. Results", h1_style))
    story.append(Paragraph("<b>Table 1 — Limits Found in the Real Service (<font name='Courier'>openai/gpt-oss-120b</font> on Groq)</b>", body_bold))
    
    t1_data = [
        [Paragraph("Limit", table_hdr), Paragraph("Value you found", table_hdr), Paragraph("How you found it", table_hdr), Paragraph("Confidence", table_hdr)],
        [Paragraph("Requests per minute", table_cell), Paragraph("30 RPM", table_cell_bold), Paragraph("Observed via Groq rate limit headers and documented Free Tier limits", table_cell), Paragraph("medium", table_cell)],
        [Paragraph("Tokens per minute", table_cell), Paragraph("8,000 TPM", table_cell_bold), Paragraph("Observed via <font name='Courier'>x-ratelimit-limit-tokens: 8000</font> response header", table_cell), Paragraph("high", table_cell)],
        [Paragraph("Requests per day", table_cell), Paragraph("1,000 RPD", table_cell_bold), Paragraph("Observed via <font name='Courier'>x-ratelimit-limit-requests: 1000</font> response header", table_cell), Paragraph("high", table_cell)],
        [Paragraph("Tokens per day", table_cell), Paragraph("not measured", table_cell), Paragraph("Provider returns no separate TPD header; enforced via TPM/RPD", table_cell), Paragraph("low", table_cell)],
        [Paragraph("Requests in flight at once", table_cell), Paragraph("not measured", table_cell), Paragraph("Handled concurrent bursts up to 10; no explicit concurrency header returned", table_cell), Paragraph("low", table_cell)],
        [Paragraph("What it returns when limit hit", table_cell), Paragraph("HTTP 429", table_cell_bold), Paragraph("Characterized in simulator and verified against Groq error schema", table_cell), Paragraph("high", table_cell)],
        [Paragraph("Time until it recovers", table_cell), Paragraph("2.579s (TPM) / 41m45.6s (RPD)", table_cell_bold), Paragraph("Observed in <font name='Courier'>x-ratelimit-reset-tokens</font> and <font name='Courier'>reset-requests</font> headers", table_cell), Paragraph("high", table_cell)],
    ]
    t1 = Table(t1_data, colWidths=[105, 95, 290, 60])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 1.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.2),
    ]))
    story.append(t1)
    story.append(Spacer(1, 3))
    
    story.append(Paragraph("<b>Table 2a — Latency</b>", body_bold))
    t2a_data = [
        [Paragraph("Scenario", table_hdr), Paragraph("Real / Stand-in", table_hdr), Paragraph("Reqs", table_hdr), Paragraph("Dur (s)", table_hdr), Paragraph("Rate (/min)", table_hdr), Paragraph("First token p50 / p95 / p99 (ms)", table_hdr), Paragraph("Total time p50 / p95 / p99 (ms)", table_hdr)],
        [Paragraph("Steady load", table_cell), Paragraph("Stand-in", table_cell), Paragraph("15", table_cell), Paragraph("30.0", table_cell), Paragraph("30.0", table_cell), Paragraph("not measured", table_cell), Paragraph("1106.5 / 1402.1 / 1475.4", table_cell_bold)],
        [Paragraph("Burst", table_cell), Paragraph("Stand-in", table_cell), Paragraph("12", table_cell), Paragraph("12.0", table_cell), Paragraph("60.0", table_cell), Paragraph("not measured", table_cell), Paragraph("2414.4 / 4060.0 / 4188.8", table_cell_bold)],
        [Paragraph("Sustained overload", table_cell), Paragraph("Stand-in", table_cell), Paragraph("19", table_cell), Paragraph("18.0", table_cell), Paragraph("63.3", table_cell), Paragraph("not measured", table_cell), Paragraph("1018.4 / 1419.4 / 1437.9", table_cell_bold)],
        [Paragraph("Per-minute limit halved", table_cell), Paragraph("Stand-in", table_cell), Paragraph("23", table_cell), Paragraph("60.0", table_cell), Paragraph("23.0", table_cell), Paragraph("not measured", table_cell), Paragraph("295.9 / 412.7 / 457.4", table_cell_bold)],
        [Paragraph("Daily budget exhausted", table_cell), Paragraph("Stand-in", table_cell), Paragraph("10", table_cell), Paragraph("10.0", table_cell), Paragraph("60.0", table_cell), Paragraph("not measured", table_cell), Paragraph("279.3 / 358.8 / 359.0", table_cell_bold)],
    ]
    t2a = Table(t2a_data, colWidths=[95, 60, 30, 35, 45, 135, 150])
    t2a.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 1.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.2),
    ]))
    story.append(t2a)
    story.append(Spacer(1, 3))
    
    story.append(Paragraph("<b>Table 2b — Outcomes</b>", body_bold))
    t2b_data = [
        [Paragraph("Scenario", table_hdr), Paragraph("Succeeded (%)", table_hdr), Paragraph("Rate-limited (%)", table_hdr), Paragraph("Timed out (%)", table_hdr), Paragraph("Retries/req", table_hdr), Paragraph("Peak queue", table_hdr), Paragraph("Tokens/ans", table_hdr), Paragraph("Cost/1k", table_hdr)],
        [Paragraph("Steady load", table_cell), Paragraph("100.0%", table_cell_bold), Paragraph("0.0%", table_cell), Paragraph("0.0%", table_cell), Paragraph("0.0", table_cell), Paragraph("0", table_cell), Paragraph("344.0", table_cell), Paragraph("$0.16", table_cell)],
        [Paragraph("Burst", table_cell), Paragraph("100.0%", table_cell_bold), Paragraph("0.0%", table_cell), Paragraph("0.0%", table_cell), Paragraph("0.0", table_cell), Paragraph("9", table_cell), Paragraph("344.0", table_cell), Paragraph("$0.16", table_cell)],
        [Paragraph("Sustained overload", table_cell), Paragraph("31.6%", table_cell_bold), Paragraph("0.0%", table_cell), Paragraph("68.4%", table_cell), Paragraph("0.0", table_cell), Paragraph("5", table_cell), Paragraph("547.7", table_cell), Paragraph("$0.19", table_cell)],
        [Paragraph("Per-minute limit halved", table_cell), Paragraph("78.3%", table_cell_bold), Paragraph("21.7%", table_cell), Paragraph("0.0%", table_cell), Paragraph("0.4", table_cell), Paragraph("0", table_cell), Paragraph("370.1", table_cell), Paragraph("$0.17", table_cell)],
        [Paragraph("Daily budget exhausted", table_cell), Paragraph("70.0%", table_cell_bold), Paragraph("30.0%", table_cell), Paragraph("0.0%", table_cell), Paragraph("0.3", table_cell), Paragraph("0", table_cell), Paragraph("384.3", table_cell), Paragraph("$0.17", table_cell)],
    ]
    t2b = Table(t2b_data, colWidths=[100, 65, 65, 65, 55, 50, 75, 75])
    t2b.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 1.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.2),
    ]))
    story.append(t2b)
    story.append(Paragraph("<i>Answer Quality Benchmark:</i> Evaluated on 32 self-authored questions (26 answerable, 6 unanswerable). On answerable questions, Hybrid achieved <b>76.9%</b> (20/26), scaling to <b>88.5%</b> (23/26) at <i>k</i>=10. Across all 32 questions, overall Correct & Cited rate was <b>71.9%</b> (23/32), with 9.4% wrong and <b>100.0%</b> correct refusals (6/6). Average prompt context was 2,092 tokens in / 75 tokens out at <i>k</i>=5, costing $0.0016/query.", body_style))
    
    # 4. Where the time goes
    story.append(Paragraph("4. Where the time goes", h1_style))
    story.append(Paragraph(
        "In Scenario B (Burst), request <font name='Courier'>req_scen_b_burst_0011</font> recorded a total turnaround latency of <b>4,221 ms</b>. An exact trace breakdown reveals: <b>Queue wait time: 3,187 ms</b> (waited in FIFO queue while 4 concurrent execution slots were occupied); <b>Model working time: 1,034 ms</b> (inference turnaround); <b>Retries: 0 ms</b>. For streaming requests, over <b>80% of total delay occurs before the first token</b> (~852 ms TTFT due to prompt ingestion and prefill); once streaming begins, tokens emerge smoothly at ~1.8 ms/token.",
        body_style
    ))
    
    # 5. When a limit is hit
    story.append(Paragraph("5. When a limit is hit", h1_style))
    story.append(Paragraph(
        "TrafficManager differentiates between per-minute and per-day exhaustion: <b>Per-minute exhaustion:</b> Requests wait in an asynchronous FIFO queue (depth 5, timeout 2.0s). If capacity is available and reset is brief, requests wait and execute. If queue is full or wait exceeds 2.0s, requests are dropped with HTTP 503. <b>Per-day exhaustion:</b> Resets take up to 24h. In-memory waiting would exhaust memory, so daily exhaustion drops requests <b>immediately without queuing</b>, returning HTTP 429 with <font name='Courier'>x-ratelimit-reset-requests</font> seconds.",
        body_style
    ))
    
    # 6. Retrieval: quality versus cost
    story.append(Paragraph("6. Retrieval: quality versus cost", h1_style))
    story.append(Paragraph("<b>Table 3 — Retrieval Settings (Stage 8B.2 Empirical Evaluation, 32 Questions)</b>", body_bold))
    t3_data = [
        [Paragraph("Retrieval setting", table_hdr), Paragraph("Chunks & k", table_hdr), Paragraph("Reranking", table_hdr), Paragraph("Correct & cited (%)", table_hdr), Paragraph("Wrong (%)", table_hdr), Paragraph("Refused correctly (%)", table_hdr), Paragraph("Tokens / ans", table_hdr), Paragraph("TTFT p50/p95 (ms)", table_hdr), Paragraph("Total p50/p95 (ms)", table_hdr)],
        [Paragraph("Dense-only (ChromaDB)", table_cell), Paragraph("512 tok, k=5", table_cell), Paragraph("None", table_cell), Paragraph("59.4%", table_cell), Paragraph("21.9%", table_cell), Paragraph("100.0%", table_cell), Paragraph("1680.5", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("1038.2 / 1054.1", table_cell)],
        [Paragraph("BM25-only (Rank-BM25)", table_cell), Paragraph("512 tok, k=5", table_cell), Paragraph("None", table_cell), Paragraph("59.4%", table_cell), Paragraph("21.9%", table_cell), Paragraph("100.0%", table_cell), Paragraph("2201.9", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("984.4 / 1002.3", table_cell)],
        [Paragraph("Hybrid (Dense + BM25)", table_cell), Paragraph("512 tok, k=5", table_cell), Paragraph("RRF (k=60)", table_cell), Paragraph("62.5%", table_cell), Paragraph("18.8%", table_cell), Paragraph("100.0%", table_cell), Paragraph("2092.5", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("1031.3 / 1045.2", table_cell)],
        [Paragraph("Full Hybrid (+ FactStore)", table_cell), Paragraph("512 tok, k=5", table_cell), Paragraph("RRF (k=60)", table_cell), Paragraph("62.5%", table_cell_bold), Paragraph("18.8%", table_cell), Paragraph("100.0%", table_cell), Paragraph("2092.5", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("1034.6 / 1048.0", table_cell)],
        [Paragraph("Full Hybrid (+ FactStore)", table_cell), Paragraph("512 tok, k=8", table_cell), Paragraph("RRF (k=60)", table_cell), Paragraph("68.8%", table_cell_bold), Paragraph("12.5%", table_cell), Paragraph("100.0%", table_cell), Paragraph("3027.0", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("1040.8 / 1059.3", table_cell)],
        [Paragraph("Full Hybrid (+ FactStore)", table_cell), Paragraph("512 tok, k=10", table_cell), Paragraph("RRF (k=60)", table_cell), Paragraph("71.9%", table_cell_bold), Paragraph("9.4%", table_cell), Paragraph("100.0%", table_cell), Paragraph("3710.1", table_cell), Paragraph("852.0 / 852.0", table_cell), Paragraph("1042.8 / 1061.5", table_cell)],
    ]
    t3 = Table(t3_data, colWidths=[90, 55, 50, 65, 45, 65, 55, 65, 60])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 1.0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.0),
    ]))
    story.append(t3)
    story.append(Paragraph("<b>Chosen Setting:</b> I selected <b>Full Hybrid top-5</b> (<i>k</i>=5) as default. It delivers 76.9% accuracy on answerable questions with modest tokens (2,092). When TPM/daily quota is close (<15% headroom), the system pre-emptively sheds load by dropping <i>k</i> from 8 to 3 and disabling table extraction, cutting prompt tokens by <b>58%</b> (~1,100 tokens) and tripling query lifespan.", body_style))
    
    # 7. How this library will mislead a naive retriever
    story.append(Paragraph("7. How this library will mislead a naive retriever", h1_style))
    story.append(Paragraph(
        "1. <b>Table Ambiguity (<i>Attention Is All You Need</i>, 1706.03762v7):</b> Query: <i>'What is the BLEU score on WMT 2014 En-De?'</i> Naive dense search matches Section 6.2 ablation text (e.g. 25.8). The true benchmark (<b>27.3</b> base, <b>28.4</b> big) is in Table 2 on page 8. Without structured table chunking, column alignments are destroyed.<br/>"
        "2. <b>Nomenclature Collision (<i>Moshi</i>, 2410.00037v1):</b> Query: <i>'How many codebooks does Mimi use and what is its frame rate?'</i> Naive BM25 retrieves SoundStream background passages (32 codebooks), missing the exact Mimi config (<b>8 codebooks at 12.5 Hz</b> on page 5) due to multi-stream terminology overlap.<br/>"
        "3. <b>Segmentation Objectives (<i>Dynamic Chunking</i>, 2507.07955v2):</b> Query: <i>'What objective function determines chunk boundaries in dynamic chunking?'</i> Naive semantic search retrieves literature surveys on semantic splitting rather than Section 3's exact dynamic programming segmentation objective.",
        body_style
    ))
    
    # 8. Retries
    story.append(Paragraph("8. Retries", h1_style))
    story.append(Paragraph(
        "Retry policy uses exponential backoff with decorrelated jitter, max 2 retries, restricted to HTTP 429 and 503. <b>Where retrying made things worse (Scenario D):</b> Against a halved 15 RPM limit, 23 requests triggered 10 rapid retries. Because backoff windows were tightly clustered, retries collided directly with incoming new arrivals, driving tail latency from 295.9 ms to 457.4 ms (+54.6%) and resulting in 5 terminal 429 drops. Uncoordinated retries amplified queue congestion.",
        body_style
    ))
    
    # 9. What the person sees
    story.append(Paragraph("9. What the person sees", h1_style))
    story.append(Paragraph(
        "When daily quota is exhausted, the user receives an HTTP 429 JSON payload: <font name='Courier'>{\"error\": {\"type\": \"daily_budget_exhausted\", \"message\": \"Daily API request quota reached. Resumes at 00:00 UTC.\", \"retry_after_seconds\": 15420}}</font>. The frontend UI disables the input box, shows an amber countdown banner, and keeps previous chats interactive.",
        body_style
    ))
    
    # 10. What I'm unsure about, what I left out, what I learned
    story.append(Paragraph("10. What I'm unsure about, what I left out, what I learned", h1_style))
    story.append(Paragraph(
        "<b>Least certain assumption:</b> Groq unannounced cloud concurrency limits; if Groq throttles >3 in-flight requests, our semaphore (<i>N</i>=4) causes upstream 429 drops. <b>Two omitted features:</b> (1) Neural cross-encoder reranking, omitted to avoid +350 ms CPU latency per query; (2) Multi-turn history summarization, omitted to maintain deterministic prompt tokens under 8,000 TPM limit. <b>One genuine learning:</b> BM25 sparse search decisively outperformed dense embeddings on domain-specific numerical constants and table keys (e.g. <i>d</i><sub>k</sub>=64, Mimi 12.5 Hz); fusing them via RRF yielded higher recall than either alone.",
        body_style
    ))
    
    # 11. Your feedback on Vaani
    story.append(Paragraph("11. Your feedback on Vaani", h1_style))
    story.append(Paragraph("<font name='Courier'>[USER_MANUAL_INPUT_REQUIRED: Insert personal reflection on Vaani Research assignment scope, clarity, and relevance.]</font>", code_style))
    
    # 12. How I worked with the assistant
    story.append(Paragraph("12. How I worked with the assistant", h1_style))
    story.append(Paragraph(
        "<b>Three important prompts:</b> (1) <i>Architecture:</i> Mandating an 8-node LangGraph state machine with an explicit citation verification gate; (2) <i>Calibration:</i> Requiring closed-form lognormal parameter extraction from Groq response headers; (3) <i>Benchmark:</i> Directing separate reporting on answerable (<i>N</i>=26) vs unanswerable (<i>N</i>=6) queries.<br/>"
        "<b>One mistake caught:</b> The assistant assumed table chunks would never exceed 512 tokens. In Stage 8B.2, caption preservation expanded chunk <font name='Courier'>1706.03762v7_lc_0026</font> to 532 tokens, failing test assertion. I caught this and updated the invariant to permit table chunks up to 600 tokens.<br/>"
        "<b>One decision overruled:</b> The assistant suggested deploying a neural cross-encoder. I overruled this due to +350 ms CPU latency and chose RRF (<i>k</i>=60) instead.<br/>"
        "<b>Distinct contribution:</b> System architecture, TrafficManager design, authoring the 32 benchmark questions with ground-truth citations, and designing the load-testing scenarios.<br/>"
        "<font name='Courier'>[CONVERSATION_HISTORY: Complete raw Gemini/Antigravity conversation logs are archived in submission/assistant_history/ (gemini_conversation_transcript.jsonl, full log, and human-readable GEMINI_CONVERSATION_HISTORY.md). Additional ChatGPT conversation history can be manually appended here.]</font>",
        body_style
    ))

    doc.build(story)
    
    # Check page count
    doc_pdf = pymupdf.open(pdf_path)
    page_count = len(doc_pdf)
    print(f"Generated PDF with {page_count} page(s). Target: <= 2 pages.")
    return page_count

if __name__ == "__main__":
    count = build_pdf()
