// PHASE2 Neo4j schema — system of record (§2.1).
// Single source of truth. Idempotent: safe to run repeatedly (IF NOT EXISTS).
// Apply with:  python -m src.graph.schema

// ── Uniqueness constraints (also create backing indexes) ─────────────────────
CREATE CONSTRAINT customer_id IF NOT EXISTS      FOR (c:Customer)     REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT conversation_id IF NOT EXISTS  FOR (c:Conversation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT intent_name IF NOT EXISTS      FOR (i:Intent)       REQUIRE i.name IS UNIQUE;
CREATE CONSTRAINT theme_name IF NOT EXISTS       FOR (t:Theme)        REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT symptom_text IF NOT EXISTS     FOR (s:Symptom)      REQUIRE s.text IS UNIQUE;
CREATE CONSTRAINT component_name IF NOT EXISTS   FOR (c:Component)    REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT rootcause_key IF NOT EXISTS    FOR (r:RootCause)    REQUIRE r.key IS UNIQUE;
CREATE CONSTRAINT action_key IF NOT EXISTS       FOR (a:Action)       REQUIRE a.key IS UNIQUE;

// ── Vector index on conversation embeddings (cosine, 384d local fastembed) ───
CREATE VECTOR INDEX conversation_embedding IF NOT EXISTS
FOR (c:Conversation) ON (c.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

// ── Full-text (Lucene BM25) index for the lexical / "sparse" retrieval arm ────
CREATE FULLTEXT INDEX conversation_fulltext IF NOT EXISTS
FOR (c:Conversation) ON EACH [c.text];
