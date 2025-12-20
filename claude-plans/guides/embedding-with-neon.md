# Embedding Data in Neon for LLM Queries

*Created: 2025-12-19*

## Overview

This guide covers how to make your Neon Postgres database searchable by LLMs using vector embeddings. This enables semantic search ("find episodes about heartbreak") rather than just keyword matching.

## When You Need Embeddings

| Use Case | Need Embeddings? | Why |
|----------|-----------------|-----|
| "Find episodes about heartbreak" | Yes | Semantic meaning search |
| "Which episodes mention Taylor Swift?" | No | SQL `WHERE description_body ILIKE '%Taylor Swift%'` |
| "Find episodes similar to this one" | Yes | Semantic similarity |
| "Summarize what the podcast says about Auto-Tune" | Yes | Need to find relevant chunks first |

If you only need keyword search, skip embeddings - just use SQL.

## Neon + pgvector

Neon supports **pgvector**, a Postgres extension for vector storage and similarity search. Everything stays in one database.

### Step 1: Enable pgvector

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 2: Add Embedding Column

```sql
-- For episode-level embeddings (good for short descriptions)
ALTER TABLE episodes ADD COLUMN embedding vector(1536);

-- Create index for fast similarity search
CREATE INDEX ON episodes USING ivfflat (embedding vector_cosine_ops);
```

Note: `1536` is the dimension for OpenAI's `text-embedding-3-small`. Other models use different dimensions.

### Step 3: Generate Embeddings

Use OpenAI API (or alternatives like Voyage, Cohere):

```typescript
import OpenAI from 'openai';

const openai = new OpenAI();

async function embedText(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text,
  });
  return response.data[0].embedding;
}

// For each episode
const embedding = await embedText(episode.description_body);
await sql`UPDATE episodes SET embedding = ${embedding} WHERE id = ${episode.id}`;
```

### Step 4: Semantic Search

```sql
-- Find 5 most similar episodes to a query
SELECT id, title, description_body
FROM episodes
WHERE embedding IS NOT NULL
ORDER BY embedding <-> $1  -- $1 is the query embedding
LIMIT 5;
```

The `<->` operator calculates cosine distance (lower = more similar).

### Step 5: Combine with SQL Filters

```sql
-- Semantic search + regular filters
SELECT id, title, description_body
FROM episodes
WHERE show_id = 1  -- Only SOP
  AND publish_date > '2020-01-01'  -- Recent episodes
  AND embedding IS NOT NULL
ORDER BY embedding <-> $1
LIMIT 5;
```

## RAG Pattern (Retrieval Augmented Generation)

The typical flow for LLM queries:

```
User Question
    ↓
Embed the question (same model used for content)
    ↓
Vector search → find top 5-10 relevant episodes
    ↓
Feed episode content to LLM as context
    ↓
LLM generates answer based on retrieved content
```

## Chunking for Long Content

If `raw_content` is too long (>8K tokens), chunk it:

```sql
CREATE TABLE episode_chunks (
  id SERIAL PRIMARY KEY,
  episode_id INTEGER REFERENCES episodes(id),
  chunk_index INTEGER,
  content TEXT,
  embedding vector(1536)
);
```

Chunking strategies:
- **Fixed size:** 500-1000 tokens per chunk with 100 token overlap
- **Semantic:** Split on paragraph/section boundaries
- **Hybrid:** Semantic splits, then size-limit each

## Cost Estimate

For the list-maker project:
- ~1,300 episodes (SOP + TAL)
- ~1,000 tokens average per episode
- OpenAI embedding cost: ~$0.02 per 1M tokens
- **Total: ~$0.03** (one-time)

Storage:
- 1536 floats × 4 bytes × 1,300 rows = ~8MB
- Well within Neon free tier (512MB limit)

## Alternative Embedding Models

| Model | Dimensions | Cost | Notes |
|-------|-----------|------|-------|
| OpenAI text-embedding-3-small | 1536 | $0.02/1M tokens | Good default |
| OpenAI text-embedding-3-large | 3072 | $0.13/1M tokens | Higher quality |
| Voyage AI | 1024 | $0.02/1M tokens | Good for code |
| Cohere embed-v3 | 1024 | Free tier available | Good alternative |

## When to Embed

- **After scraping is complete** - don't embed incrementally during scrape
- **Once per content version** - re-embed if you significantly change description_body
- **Batch process** - embed all episodes in one script run

## Example: Full Implementation

```typescript
// embed-episodes.ts
import { neon } from '@neondatabase/serverless';
import OpenAI from 'openai';

const sql = neon(process.env.DATABASE_URL!);
const openai = new OpenAI();

async function embedAllEpisodes() {
  // Get episodes without embeddings
  const episodes = await sql`
    SELECT id, description_body
    FROM episodes
    WHERE embedding IS NULL AND description_body IS NOT NULL
  `;

  for (const ep of episodes) {
    const response = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: ep.description_body,
    });

    const embedding = response.data[0].embedding;

    await sql`
      UPDATE episodes
      SET embedding = ${JSON.stringify(embedding)}::vector
      WHERE id = ${ep.id}
    `;

    console.log(`Embedded episode ${ep.id}`);

    // Rate limit: 3000 RPM for OpenAI
    await new Promise(r => setTimeout(r, 50));
  }
}

embedAllEpisodes();
```

## Resources

- [Neon pgvector docs](https://neon.tech/docs/extensions/pgvector)
- [OpenAI Embeddings guide](https://platform.openai.com/docs/guides/embeddings)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
