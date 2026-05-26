import os
import re
import json
import logging
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings
from app.services.llm_service import llm_service

logger = logging.getLogger("rag_service")

class RAGService:
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.bm25_idf: Dict[str, float] = {}
        self.avg_doc_len: float = 0.0
        self.doc_lens: List[int] = []
        self.doc_term_freqs: List[Dict[str, int]] = []
        self.vector_store_path = os.path.join(settings.MEMORIES_DIR, "vector_store.json")
        self.api_key: Optional[str] = None
        self.load_index()

    def chunk_text(self, text: str, source: str, chunk_size: int = 800, overlap: int = 150) -> List[Dict[str, Any]]:
        """Splits text into overlapping chunks, attempting to split at sentence boundaries."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_length + sentence_len > chunk_size and current_chunk:
                chunk_content = " ".join(current_chunk)
                chunks.append({
                    "text": chunk_content,
                    "metadata": {
                        "source": source,
                        "char_count": len(chunk_content),
                        "chunk_index": len(chunks)
                    }
                })
                # Handle overlap: keep last few sentences that fit in the overlap window
                overlap_chunk = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) < overlap:
                        overlap_chunk.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = overlap_len

            current_chunk.append(sentence)
            current_length += sentence_len

        if current_chunk:
            chunk_content = " ".join(current_chunk)
            chunks.append({
                "text": chunk_content,
                "metadata": {
                    "source": source,
                    "char_count": len(chunk_content),
                    "chunk_index": len(chunks)
                }
            })

        return chunks

    def _get_embedding(self, text: str) -> List[float]:
        """Generates embedding using OpenAI, falling back to mock random vector if unconfigured."""
        client = llm_service.openai_client
        if self.api_key:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
        elif not llm_service.openai_configured:
            return self._get_embedding_mock(text)
            
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}. Falling back to mock.")
            return self._get_embedding_mock(text)

    def _get_embedding_mock(self, text: str) -> List[float]:
        h = hash(text)
        np.random.seed(abs(h) % (2**32))
        return np.random.randn(768).tolist()

    def build_index_from_files(self, file_paths: List[str], api_key: Optional[str] = None):
        """Reads files, chunks them, generates embeddings in batches, builds BM25 and saves index."""
        logger.info(f"Building RAG index from {len(file_paths)} files.")
        self.api_key = api_key
        new_chunks = []
        for path in file_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                basename = os.path.basename(path)
                file_chunks = self.chunk_text(text, source=basename)
                new_chunks.extend(file_chunks)
                logger.info(f"Chunked {basename} into {len(file_chunks)} chunks.")
            except Exception as e:
                logger.error(f"Error reading {path}: {e}")

        if not new_chunks:
            logger.warning("No text chunks created. Index build aborted.")
            return

        self.chunks = new_chunks
        
        # Build Dense Embeddings Matrix in batches
        logger.info(f"Embedding {len(self.chunks)} chunks in batch mode.")
        embeddings_list = []
        
        client = llm_service.openai_client
        if self.api_key:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
        is_openai_avail = llm_service.openai_configured or self.api_key
        
        if is_openai_avail:
            try:
                texts = [c["text"] for c in self.chunks]
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                embeddings_list = [x.embedding for x in response.data]
                for i, emb in enumerate(embeddings_list):
                    self.chunks[i]["embedding"] = emb
            except Exception as e:
                logger.error(f"Batch OpenAI embedding failed: {e}. Falling back to individual embedding.")
                embeddings_list = []
                for i, chunk in enumerate(self.chunks):
                    emb = self._get_embedding(chunk["text"])
                    embeddings_list.append(emb)
                    chunk["embedding"] = emb
        else: # Mock
            for chunk in self.chunks:
                emb = self._get_embedding(chunk["text"])
                embeddings_list.append(emb)
                chunk["embedding"] = emb

        self.embeddings = np.array(embeddings_list)
        
        # Build BM25 Index
        self._build_bm25()
        self.save_index()

    def _build_bm25(self):
        """Builds term-frequency lists and IDF values for BM25 search."""
        self.doc_lens = []
        self.doc_term_freqs = []
        
        # Simple word tokenization
        def tokenize(text: str) -> List[str]:
            return re.findall(r'\b\w+\b', text.lower())

        word_dfs = {}
        for chunk in self.chunks:
            tokens = tokenize(chunk["text"])
            self.doc_lens.append(len(tokens))
            
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freqs.append(tf)
            
            # Unique words for document frequency (df)
            for t in tf.keys():
                word_dfs[t] = word_dfs.get(t, 0) + 1

        self.avg_doc_len = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0
        
        # Calculate IDF
        N = len(self.chunks)
        self.bm25_idf = {}
        for term, df in word_dfs.items():
            # BM25 standard IDF with smoothing
            self.bm25_idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    def _search_bm25(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Calculates BM25 relevance scores for all chunks."""
        tokens = re.findall(r'\b\w+\b', query.lower())
        scores = []
        
        k1 = 1.5
        b = 0.75
        
        for idx, tf in enumerate(self.doc_term_freqs):
            score = 0.0
            doc_len = self.doc_lens[idx]
            for token in tokens:
                if token in tf:
                    term_tf = tf[token]
                    idf = self.bm25_idf.get(token, 0.0)
                    # BM25 formula
                    numerator = term_tf * (k1 + 1)
                    denominator = term_tf + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len))
                    score += idf * (numerator / denominator)
            scores.append((idx, score))
            
        # Normalize BM25 scores between 0 and 1
        if scores:
            max_score = max(s[1] for s in scores)
            if max_score > 0:
                scores = [(idx, s / max_score) for idx, s in scores]
                
        return sorted(scores, key=lambda x: x[1], reverse=True)[:top_k]

    def _search_dense(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Calculates cosine similarity of query embedding with all chunk embeddings."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []
            
        q_emb = np.array(self._get_embedding(query))
        
        # Calculate cosine similarities
        norms = np.linalg.norm(self.embeddings, axis=1)
        q_norm = np.linalg.norm(q_emb)
        
        if q_norm == 0:
            return [(i, 0.0) for i in range(len(self.chunks))]
            
        # Cosine similarity
        similarities = np.dot(self.embeddings, q_emb) / (norms * q_norm + 1e-9)
        
        # Map to index and score
        scores = [(idx, float(sim)) for idx, sim in enumerate(similarities)]
        
        # Normalize to 0-1 (cosine similarity ranges -1 to 1, but we shift/scale to 0-1)
        scores = [(idx, (sim + 1.0) / 2.0) for idx, sim in scores]
        
        return sorted(scores, key=lambda x: x[1], reverse=True)[:top_k]

    def hybrid_search(self, query: str, top_k: int = 5, dense_weight: float = 0.5, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Combines BM25 and Dense vector search results with a weighted fusion, then reranks."""
        if not self.chunks:
            return []
            
        # Temporarily use query api key if provided
        if api_key:
            self.api_key = api_key

        # Get top candidates from both search methods
        dense_results = self._search_dense(query, top_k=max(20, top_k * 3))
        bm25_results = self._search_bm25(query, top_k=max(20, top_k * 3))
        
        # Merge scores
        merged_scores = {}
        for idx, score in dense_results:
            merged_scores[idx] = merged_scores.get(idx, 0.0) + score * dense_weight
            
        for idx, score in bm25_results:
            merged_scores[idx] = merged_scores.get(idx, 0.0) + score * (1.0 - dense_weight)
            
        # Sort and take top candidates for rerank
        sorted_candidates = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Perform LLM-based Reranking
        reranked_results = self._llm_rerank(query, sorted_candidates, top_k=top_k, api_key=api_key)
        
        return reranked_results

    def _llm_rerank(self, query: str, candidates: List[Tuple[int, float]], top_k: int, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Uses LLM-as-judge to rank candidate chunks by relevance to the query."""
        if not candidates:
            return []
            
        # Extract candidate text segments
        candidate_items = []
        for idx, score in candidates:
            candidate_items.append({
                "index": idx,
                "text": self.chunks[idx]["text"]
            })
            
        prompt = f"""You are an Information Retrieval Rerank Agent. 
Evaluate the relevance of the following document chunks to the search query: "{query}"

For each chunk, assign a relevance score from 0 to 10 (where 0 means completely irrelevant and 10 means extremely relevant/answers the query directly).
Return the result in JSON format under the key "reranked" containing an array of objects:
[
  {{"index": <index>, "score": <0-10 score>, "reason": "<brief justification>"}}
]

Chunks to rank:
{json.dumps(candidate_items, indent=2)}
"""
        try:
            # Run fast model (flash) for reranking
            res_str = llm_service.generate_text(
                prompt=prompt,
                system_instruction="You rank search results for accuracy and relevance. Reply in structured JSON.",
                model_type="flash",
                agent_name="Reranker",
                api_key=api_key
            )
            
            # Parse output
            # Extract JSON if markdown wrapped
            match = re.search(r'\{.*\}', res_str, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                data = json.loads(res_str)
                
            scores_dict = {item["index"]: item["score"] for item in data["reranked"]}
            
            # Re-sort candidates based on LLM score
            final_list = []
            for idx, old_score in candidates:
                llm_score = scores_dict.get(idx, 0.0)
                # Combine old retrieval score (scaled to 0-10) and LLM score (0-10)
                combined_score = (old_score * 10.0) * 0.3 + llm_score * 0.7
                final_list.append((idx, combined_score))
                
            final_list = sorted(final_list, key=lambda x: x[1], reverse=True)[:top_k]
            
            # Map back to chunk objects
            results = []
            for idx, score in final_list:
                chunk = self.chunks[idx].copy()
                if "embedding" in chunk:
                    del chunk["embedding"]  # Remove embedding vectors before sending over JSON api
                chunk["score"] = score
                results.append(chunk)
            return results
            
        except Exception as e:
            logger.error(f"LLM reranking failed: {e}. Falling back to default retrieval scoring.")
            # Fallback to dense/BM25 scores
            results = []
            for idx, score in candidates[:top_k]:
                chunk = self.chunks[idx].copy()
                if "embedding" in chunk:
                    del chunk["embedding"]
                chunk["score"] = score * 10.0
                results.append(chunk)
            return results

    def save_index(self):
        """Saves current chunks, BM25 lists, and embeddings to JSON."""
        if not self.chunks:
            return
        try:
            # We construct a serializable dictionary
            serializable_chunks = []
            for c in self.chunks:
                sc = c.copy()
                # Embedding is already serializable list
                serializable_chunks.append(sc)
                
            data = {
                "chunks": serializable_chunks,
                "avg_doc_len": self.avg_doc_len,
                "doc_lens": self.doc_lens,
                "bm25_idf": self.bm25_idf,
                "doc_term_freqs": self.doc_term_freqs
            }
            with open(self.vector_store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("RAG index saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save RAG index: {e}")

    def load_index(self):
        """Loads chunks, BM25 lists, and embeddings from JSON if file exists."""
        if not os.path.exists(self.vector_store_path):
            logger.info("No vector store index found. Ready to initialize.")
            return
            
        try:
            with open(self.vector_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.chunks = data["chunks"]
            self.avg_doc_len = data["avg_doc_len"]
            self.doc_lens = data["doc_lens"]
            self.bm25_idf = data["bm25_idf"]
            self.doc_term_freqs = data["doc_term_freqs"]
            
            # Reconstruct embeddings array
            embeddings_list = []
            for c in self.chunks:
                if "embedding" in c:
                    embeddings_list.append(c["embedding"])
            if embeddings_list:
                self.embeddings = np.array(embeddings_list)
            logger.info(f"Loaded RAG index with {len(self.chunks)} chunks.")
        except Exception as e:
            logger.error(f"Failed to load RAG index: {e}")

rag_service = RAGService()
