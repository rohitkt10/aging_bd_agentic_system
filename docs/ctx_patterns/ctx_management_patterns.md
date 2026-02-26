# Agentic Memory Management: Architectural Patterns and Implementation Roadmap

## 1. Motivation & Problem Statement

The objective is to architect an autonomous ReAct loop capable of executing high-fidelity biomedical research tasks—specifically, curating gene lists and GO terms related to the hallmarks of aging and their underlying biological processes. In such systems, reasoning spans multiple tool-calling iterations, generating discrete, non-temporal facts scattered across literature and genomic databases.

LLMs inherently suffer from context window degradation (the "lost in the middle" phenomenon) and struggle to synthesize contradictory or widely separated facts presented in a flat, chronological log. Aging biology is highly pleiotropic; a single gene like *mTOR* or *SIRT1* may have conflicting evidence depending on the tissue context or specific aging hallmark. Effective agentic memory must evolve from a passive transcript of ReAct actions into an active, queryable, and structured state representation to maintain reasoning coherence and output accuracy.

## 2. Current State Assessment

Based on the existing `phase2_research` implementation, the agent utilizes a **Temporal Append-Only Scratchpad**.

* **Mechanism:** Findings from GenAge, OpenGenes, PubMed, and local vector stores are continuously appended to a JSON array (`research_data["research_findings"].extend(new_findings)`).
* **Compression:** Context length is managed via chronological text summarization (`summarize_if_needed`).
* **Failure Modes:** 1.  **Temporal Bias:** Early, high-value evidence (e.g., a definitive knockout study found in iteration 1) may be aggressively summarized or entirely truncated as the context window fills, while recent, low-value evidence dominates the active prompt.
2.  **Disconnected Facts:** A finding about a gene in iteration 1 and another in iteration 5 are not naturally synthesized. The LLM is forced to hold these unlinked entities in its latent space and resolve them in a zero-shot manner during the final `summarize_for_scoring` phase, increasing hallucination risk.
3.  **Token Wastage:** Passing the entire history of "dead-end" searches consumes tokens without contributing to the final synthesis.

## 3. Proposed Memory Architectures (Mental Models)

### 3.1 Semantic Memory (Vector-Based Retrieval)

Instead of summarizing a chronological list, individual findings are embedded and retrieved based solely on semantic relevance to the agent's current cognitive step.

* **Mental Model:** The agent utilizes an external, searchable index card system. It retrieves only the exact evidence required to validate a specific hypothesis, ignoring discovery order.
* **Implementation Abstraction:**
* Deprecate the `research_findings` list.
* Instantiate an ephemeral, in-memory vector store (e.g., FAISS, Chroma) at `current_iteration == 0`.
* **Write:** Upon receiving tool outputs, the agent maps them to document chunks: `vector_store.add(Document(text=new_finding, metadata={"target_gene": "mTOR", "source": "pubmed_abstract"}))`.
* **Read:** During the `PHASE2_DECISION_USER_PROMPT`, inject context dynamically via `vector_store.similarity_search(query=current_focus, k=5)`.


* **Trade-offs:** Effectively solves context overflow and is relatively simple to implement. However, it does not inherently resolve biological contradictions; it merely surfaces them.

### 3.2 Structured Entity Memory (Knowledge Graphs)

Memory is explicitly maintained as a dynamic directed graph. Nodes represent biological entities (genes, biological processes, aging hallmarks), and edges represent the evidence-backed relationships.

* **Mental Model:** The agent constructs a localized biological network map. New literature findings do not merely add text to a file; they create or strengthen specific topological connections.
* **Implementation Abstraction:**
* Modify the LLM structured output schema to extract RDF-style triples: `(Subject, Predicate, Object, Evidence_Snippet)`.
* *Pseudo-schema:* `{"subject": "SIRT1", "relation": "maintains", "object": "genomic stability", "confidence_score": 0.8}`
* **State Management:** Maintain this graph using a lightweight library like `networkx`. The context passed to the LLM is a textual rendering of the graph neighborhood directly surrounding the current Biological Process.


* **Trade-offs:** Provides the highest fidelity for complex biomedical reasoning and naturally resolves disconnected facts. However, it requires complex schema engineering and prompt tuning to ensure consistent entity normalization (e.g., resolving "SIRT-1" vs "SIRT1").

### 3.3 Hierarchical Memory (Tiered Storage)

Memory is partitioned by scope and lifespan, preventing context contamination between distinct research targets in the queue.

* **Mental Model:** Human cognitive architecture (Working Memory $\rightarrow$ Episodic Memory $\rightarrow$ Semantic Long-Term Memory).
* **Implementation Abstraction:**
* **Level 1 (Working):** Active context window containing only the current iteration's raw tool outputs. Flushed every iteration.
* **Level 2 (Episodic):** The synthesized state of the *current* Biological Process (e.g., "Cellular Senescence"). Flushed during `advance_bp`.
* **Level 3 (Archival):** A persistent database mapping finalized genes across *all* processed BPs and hallmarks.
* **Workflow:** When initializing a new BP (e.g., "Telomere Attrition"), query Level 3 to inject prior relevant discoveries into Level 2 (e.g., "Previously identified FOXO3 in Stem Cell Exhaustion; evaluate for cross-talk").


* **Trade-offs:** Highly effective for sequential pipeline execution (`bp_queue`), but requires rigid state boundaries and state-routing logic.

### 3.4 Reflective Memory (Self-Editing State)

The scratchpad is treated as a mutable state object. The agent is equipped with specific tools to explicitly rewrite, prune, and synthesize this state at every iteration.

* **Mental Model:** A Wikipedia article editor. The agent continuously revises a master document as new sources are reviewed, rather than acting as a court reporter logging an immutable transcript.
* **Implementation Abstraction:**
* Define a strict Pydantic model for the state: `{"active_hypotheses": [], "validated_genes": { "symbol": {"score": int, "evidence": str, "citations": []} }, "unresolved_conflicts": []}`.
* Provide state mutation tools alongside research tools: `upsert_gene_evidence(gene, new_evidence)`, `flag_contradiction(gene, claim1, claim2)`, `drop_weak_candidate(gene)`.
* Every ReAct iteration, the agent must decide to either gather more data via search tools or consolidate its memory via mutation tools.


* **Trade-offs:** Maximizes context density and reasoning quality by forcing iterative conflict resolution. The finalized state object *is* the final output, eliminating the need for a separate scoring phase. However, it increases token usage per iteration due to passing the full, structured state back and forth.

## 4. Implementation Roadmap

For a biomedical RAG system focused on gene curation across aging hallmarks, **Reflective Memory** provides the most robust solution for evidence synthesis, eliminating the reliance on flawed chronological summarization.

**Recommended Migration Plan:**

1. **Phase 1 (Data Structure Refactoring):** * Deprecate the `research_findings` list and `summarize_if_needed` utility.
* Implement a structured `RefinedEvidenceState` dictionary within the main agent state.


2. **Phase 2 (Action Schema Expansion):** * Update `decision_schema` properties. Alongside the `actions` array (for querying PubMed/GenAge), introduce a `state_updates` array.
* Require the LLM to output specific CRUD operations (Create, Read, Update, Delete) against the `RefinedEvidenceState` based on the newly acquired information.


3. **Phase 3 (Prompt & Pipeline Optimization):** * Rewrite `PHASE2_DECISION_USER_PROMPT` to pass the current `RefinedEvidenceState` instead of a raw finding summary.
* Remove the final `summarize_for_scoring` LLM call. The loop terminates when `max_iterations` is reached or when the LLM determines the `RefinedEvidenceState` has met a predefined confidence threshold, yielding the state object directly as the final output.