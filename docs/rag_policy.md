# RAG Policy

## Purpose

RAG exists to make Forge grounded in curated knowledge.

RAG should not become a garbage dump of the user's whole computer.

## What belongs in RAG

- project briefs
- SOPs
- architecture docs
- style guides
- glossary files
- research notes
- manuals
- public references
- curated examples

## What does not belong in RAG

- secrets
- credentials
- SSH keys
- raw browser profiles
- entire downloads folder
- duplicate files
- untrusted scraped pages without labels
- volatile logs unless the module is specifically built for log analysis

## Chunking policy

Recommended default:

- Markdown: split by headings, then by 600-900 tokens
- Code: split by symbols/classes/functions where possible
- PDFs: extract text and preserve page numbers
- Tables: preserve row/column context
- Overlap: 80-120 tokens

## Retrieval policy

Default retrieval:

- top_k vector candidates: 20
- rerank top_k: 8
- final context chunks: 4-6
- always include source path and chunk heading
- never cite a source that was not actually retrieved

## Conflict policy

If RAG and live files disagree:

1. prefer live files for current implementation state
2. cite both
3. report the conflict
4. ask whether the source should be updated
