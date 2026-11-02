# DocMind Evaluation Results

Run against 10 bundled questions. Retrieval metrics use the expected source document; answer quality was judged by the configured LLM for hybrid retrieval with reranking. Scores are in the range 0–1.

| Retrieval mode | Hit@5 | MRR |
|---|---:|---:|
| vector | 1.000 | 1.000 |
| bm25 | 1.000 | 1.000 |
| hybrid + rerank | 1.000 | 1.000 |

| Hybrid + rerank answer quality | Score |
|---|---:|
| Faithfulness | 1.000 |
| Answer relevance | 1.000 |
