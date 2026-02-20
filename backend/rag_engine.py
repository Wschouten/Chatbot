"""RAG Engine for configurable brand Chatbot."""

from __future__ import annotations  # MUST be first

import glob
import logging
import os
import time
from typing import Any, Optional

from brand_config import get_brand_config

logger = logging.getLogger(__name__)

# -----------------------------
# OpenAI Client State
# -----------------------------
_openai_client = None
_openai_init_error: Optional[str] = None


# -----------------------------
# OpenAI Client Management
# -----------------------------
def get_openai_client():
    """
    Lazy-initialize and return a cached OpenAI client.
    This ensures all parts of the app (including /health) see the same state.
    """
    global _openai_client, _openai_init_error

    if _openai_client is not None:
        return _openai_client

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        _openai_init_error = "OPENAI_API_KEY is missing"
        logger.error(_openai_init_error)
        return None

    try:
        from openai import OpenAI  # imported lazily

        _openai_client = OpenAI(api_key=api_key)
        _openai_init_error = None
        logger.info("OpenAI Client Initialized Successfully.")
        return _openai_client
    except Exception as exc:
        _openai_client = None
        _openai_init_error = f"{type(exc).__name__}: {exc}"
        logger.exception("OpenAI client initialization failed.")
        return None


def get_openai_health() -> dict:
    """
    Returns a health payload without exposing secrets.
    """
    client = get_openai_client()
    if client is None:
        return {
            "status": "unhealthy",
            "message": _openai_init_error or "Client not initialized",
        }

    return {"status": "healthy"}



# Configure logging
logger = logging.getLogger(__name__)

# Try imports for RAG specific libraries (incompatible with Py 3.14)
try:
    import chromadb
    from pypdf import PdfReader
    RAG_DEPENDENCIES_LOADED = True
except Exception as e:
    logger.warning("RAG Libraries (ChromaDB/PyPDF) incompatible or missing: %s", e)
    RAG_DEPENDENCIES_LOADED = False
    chromadb = None  # type: ignore
    PdfReader = None  # type: ignore


class RagEngine:
    """RAG Engine for document-based question answering."""

    def __init__(
        self,
        knowledge_base_path: str = "./knowledge_base",
        persist_directory: str = "./chroma_db"
    ) -> None:
        """Initialize the RAG Engine."""
        self.knowledge_base_path = knowledge_base_path
        self.persist_directory = persist_directory
        self.collection_name = "groundcovergroup_docs"
        self.openai_client: Any = None
        self.collection: Any = None
        self.chroma_client: Any = None

        # Feature 10: Make LLM Model Configurable
        self.chat_model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-5.2')
        self.embedding_model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')

        # Feature 13: Retrieval Quality Improvements
        self.relevance_threshold = float(os.getenv('RAG_RELEVANCE_THRESHOLD', '1.2'))

        # RAG result caching for session consistency
        self.session_cache: dict[str, tuple[str, float]] = {}  # query -> (context, timestamp)
        self.cache_ttl: float = 300.0  # 5 minutes cache TTL

        # Initialize OpenAI (uses the lazy singleton from get_openai_client)
        self.openai_client = get_openai_client()

        # Initialize ChromaDB (Only if dependencies loaded)
        # Retry once after a short delay to handle gunicorn worker race conditions
        # where multiple workers compete for SQLite migration locks
        if RAG_DEPENDENCIES_LOADED and chromadb:
            for attempt in range(2):
                try:
                    self.chroma_client = chromadb.PersistentClient(path=self.persist_directory)
                    self.collection = self.chroma_client.get_or_create_collection(
                        name=self.collection_name
                    )
                    logger.info("Knowledge Base Initialized.")
                    break
                except Exception as e:
                    if attempt == 0:
                        logger.warning("ChromaDB init failed (attempt 1), retrying: %s", e)
                        time.sleep(2)
                    else:
                        logger.error("ChromaDB Initialization Error: %s", e)
                        self.collection = None
        else:
            logger.warning("Running without Knowledge Base (Memory).")

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using OpenAI."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")
        response = self.openai_client.embeddings.create(
            input=text,
            model=self.embedding_model
        )
        return response.data[0].embedding

    def _reformulate_query(
        self,
        query: str,
        chat_history: list[dict[str, str]]
    ) -> str:
        """Reformulate a follow-up question into a standalone query using conversation context."""
        if not self.openai_client:
            return query

        try:
            # Use last 6 messages instead of 4 for better context
            recent = chat_history[-6:]

            # Don't truncate content - use full messages for entity preservation
            history_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
                for m in recent
            )

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You rewrite follow-up questions into standalone questions. "
                            "Use the conversation history to resolve pronouns and references. "
                            "CRITICAL: Always preserve product names, specific items, and entities from the conversation. "
                            "If a product was mentioned (e.g., 'cacaodoppen'), include it in the rewritten query. "
                            "Keep the language of the user's question "
                            "(Dutch stays Dutch, English stays English). "
                            "If the question is already standalone, return it unchanged. "
                            "Output ONLY the rewritten question, nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Conversation history:\n{history_text}\n\n"
                            f"Follow-up question: {query}\n\n"
                            "Rewritten standalone question:"
                        )
                    }
                ],
                temperature=0.0,
                max_completion_tokens=150
            )
            result = response.choices[0].message.content
            if result:
                reformulated = result.strip()
                logger.debug("Query reformulated: '%s' -> '%s'", query, reformulated)
                return reformulated
            return query
        except Exception as e:
            logger.warning("Query reformulation failed, using original: %s", e)
            return query

    def _get_cached_context(self, query: str) -> Optional[str]:
        """Get cached RAG context if available and not stale."""
        import time

        if query in self.session_cache:
            context, timestamp = self.session_cache[query]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug("Using cached context for query: '%s'", query)
                return context
            else:
                # Clean up stale entry
                del self.session_cache[query]
        return None

    def _cache_context(self, query: str, context: str) -> None:
        """Cache RAG context for this query."""
        import time
        self.session_cache[query] = (context, time.time())

        # Clean up old entries (keep max 50)
        if len(self.session_cache) > 50:
            sorted_items = sorted(
                self.session_cache.items(),
                key=lambda x: x[1][1]
            )
            # Remove oldest 10
            for key, _ in sorted_items[:10]:
                del self.session_cache[key]

    def _extract_conversation_entities(self, chat_history: list[dict[str, str]]) -> list[str]:
        """Extract product names and key entities from recent conversation.

        Returns a list of important terms/products that should be considered
        in the current query context.
        """
        if not chat_history or not self.openai_client:
            return []

        try:
            # Look at last 4 messages for entity extraction
            recent = chat_history[-4:]
            history_text = "\n".join(
                f"{m['role']}: {m['content'][:500]}"
                for m in recent
            )

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract product names, specific items, and key entities from this conversation. "
                            "Return ONLY a comma-separated list of terms, or 'NONE' if there are no specific entities. "
                            "Focus on concrete nouns like product names, not general concepts."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Conversation:\n{history_text}\n\nEntities:"
                    }
                ],
                temperature=0.0,
                max_completion_tokens=50
            )

            result = response.choices[0].message.content
            if result and result.strip().upper() != 'NONE':
                entities = [e.strip() for e in result.split(',') if e.strip()]
                logger.debug("Extracted conversation entities: %s", entities)
                return entities
            return []
        except Exception as e:
            logger.warning("Entity extraction failed: %s", e)
            return []

    def _extract_metadata_from_content(self, content: str, filename: str) -> dict[str, str]:
        """Extract metadata from document content.

        Feature 12: Knowledge Base Metadata

        Checks first line for # PRODUCT: or # KENNIS: headers and extracts
        category from ## Categorie section.

        Args:
            content: The full document content
            filename: The source filename

        Returns:
            Dict with metadata fields: doc_type, product_name/topic, category
        """
        metadata: dict[str, str] = {}
        lines = content.split('\n')

        # Check first line for document type
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith('# PRODUCT:'):
                metadata['doc_type'] = 'product'
                metadata['product_name'] = first_line.replace('# PRODUCT:', '').strip()
            elif first_line.startswith('# KENNIS:'):
                metadata['doc_type'] = 'knowledge'
                metadata['topic'] = first_line.replace('# KENNIS:', '').strip()

        # Extract category from ## Categorie section
        for i, line in enumerate(lines):
            if line.strip() == '## Categorie':
                # Category text is on the next line
                if i + 1 < len(lines):
                    metadata['category'] = lines[i + 1].strip()
                break

        return metadata

    def _ingest_text_chunks(
        self,
        full_text: str,
        source_id: str,
        chunk_size: int = 2000,
        overlap: int = 200,
        file_metadata: Optional[dict[str, str]] = None
    ) -> int:
        """Chunk and ingest text into ChromaDB. Returns number of chunks created."""
        if not self.collection:
            return 0

        text_len = len(full_text)
        start = 0
        chunk_index = 0

        while start < text_len:
            end = start + chunk_size
            chunk = full_text[start:end]

            # Try to find the last newline to break cleanly
            if end < text_len:
                last_newline = chunk.rfind('\n')
                if last_newline != -1 and last_newline > chunk_size * 0.5:
                    end = start + last_newline + 1
                    chunk = full_text[start:end]

            if chunk.strip():
                try:
                    emb = self._get_embedding(chunk)

                    # Feature 12: Merge file metadata with chunk metadata
                    chunk_metadata = {"source": source_id, "chunk": chunk_index}
                    if file_metadata:
                        chunk_metadata.update(file_metadata)

                    self.collection.add(
                        documents=[chunk],
                        embeddings=[emb],
                        metadatas=[chunk_metadata],
                        ids=[f"{source_id}_chunk_{chunk_index}"]
                    )
                    chunk_index += 1
                except Exception as e:
                    logger.error("Error embedding chunk %d of %s: %s", chunk_index, source_id, e)

            # Move forward, subtracting overlap to keep context
            start = end - overlap
            if start < 0:
                start = 0
            if start >= text_len:
                break

            # Avoid infinite loops
            if end <= start:
                start = end

        return chunk_index

    def _cleanup_stale_entries(self) -> int:
        """Remove ChromaDB entries for files no longer on disk.

        Returns the number of stale sources removed.
        """
        if not self.collection:
            return 0

        total = self.collection.count()
        if total == 0:
            return 0

        # Fetch all metadata to find unique source filenames
        all_data = self.collection.get(limit=total, include=["metadatas"])

        indexed_sources: set[str] = set()
        for metadata in all_data["metadatas"]:
            if metadata and "source" in metadata:
                indexed_sources.add(metadata["source"])

        if not indexed_sources:
            return 0

        # Build set of current filenames on disk
        current_files: set[str] = set()
        for ext in ("*.txt", "*.pdf"):
            for file_path in glob.glob(os.path.join(self.knowledge_base_path, ext)):
                current_files.add(os.path.basename(file_path))

        # Find and remove stale sources
        stale_sources = indexed_sources - current_files
        removed = 0
        for source_name in stale_sources:
            try:
                self.collection.delete(where={"source": source_name})
                logger.info("Removed stale entries for: %s", source_name)
                removed += 1
            except Exception as e:
                logger.error("Error removing stale entries for %s: %s", source_name, e)

        return removed

    def ingest_documents(self) -> str:
        """Load PDFs/TXTs, chunk them, and save to ChromaDB.

        Also removes stale entries for files that no longer exist on disk.
        """
        if not RAG_DEPENDENCIES_LOADED or not self.collection:
            return "Knowledge Base unavailable. Documents will not be indexed."

        if not os.path.exists(self.knowledge_base_path):
            os.makedirs(self.knowledge_base_path)
            return "Knowledge base directory created."

        # Phase 1: Clean up stale entries for deleted files
        removed = self._cleanup_stale_entries()

        # Phase 2: Ingest new files
        existing_ids: set[str] = set()
        try:
            total = self.collection.count()
            if total > 0:
                existing_ids = set(
                    self.collection.get(limit=total, include=[])['ids']
                )
        except Exception:
            pass

        count = 0
        skipped = 0

        # Process .txt files
        for file_path in glob.glob(os.path.join(self.knowledge_base_path, "*.txt")):
            file_id = os.path.basename(file_path)
            if f"{file_id}_chunk_0" in existing_ids:
                skipped += 1
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                    if text.strip():
                        # Feature 12: Extract metadata and pass to ingest
                        file_metadata = self._extract_metadata_from_content(text, file_id)
                        self._ingest_text_chunks(text, file_id, file_metadata=file_metadata)
                        count += 1
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="utf-8-sig") as f:
                        text = f.read()
                        if text.strip():
                            # Feature 12: Extract metadata and pass to ingest
                            file_metadata = self._extract_metadata_from_content(text, file_id)
                            self._ingest_text_chunks(text, file_id, file_metadata=file_metadata)
                            count += 1
                except Exception as e:
                    logger.error("Error reading %s (encoding fallback): %s", file_path, e)
            except Exception as e:
                logger.error("Error reading %s: %s", file_path, e)

        # Process .pdf files
        for file_path in glob.glob(os.path.join(self.knowledge_base_path, "*.pdf")):
            file_id = os.path.basename(file_path)
            if f"{file_id}_chunk_0" in existing_ids:
                skipped += 1
                continue

            try:
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"

                if text.strip():
                    # Feature 12: Extract metadata and pass to ingest
                    file_metadata = self._extract_metadata_from_content(text, file_id)
                    self._ingest_text_chunks(text, file_id, file_metadata=file_metadata)
                    count += 1
            except Exception as e:
                logger.error("Error reading PDF %s: %s", file_path, e)

        return (
            f"Ingestion Complete. {count} new documents processed. "
            f"{skipped} skipped. {removed} stale sources removed."
        )

    def get_answer(
        self,
        query: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        language: str = 'nl'
    ) -> str:
        """Get answer to a query using RAG.

        Args:
            query: The user's question
            chat_history: Optional list of previous messages, each with 'role' and 'content'
            language: Detected language ('nl' or 'en')
        """
        if not self.openai_client:
            return "Error: OpenAI API Key invalid or client not initialized."

        # Get brand configuration
        brand = get_brand_config()

        context = ""

        # Feature 15: Select personality and hints based on detected language
        if language == 'en':
            personality = brand.personality_en
            emoji_hint = "Use an occasional emoji to keep the conversation warm (🌱, 👍, 🤔). " if brand.use_emojis else ""
        else:
            personality = brand.personality_nl
            emoji_hint = "Gebruik af en toe een emoji om het gesprek warm te houden (🌱, 👍, 🤔). " if brand.use_emojis else ""

        system_prompt = (
            f"{personality}\n\n"
            f"{emoji_hint}"
        )

        # Attempt to get context if RAG is working
        if RAG_DEPENDENCIES_LOADED and self.collection:
            try:
                # Feature 15: Translate English queries to Dutch for better KB matching
                search_query = query

                # Feature 25: Reformulate follow-up questions into standalone queries
                if chat_history:
                    # Extract entities from conversation for context-aware search
                    conversation_entities = self._extract_conversation_entities(chat_history)

                    search_query = self._reformulate_query(query, chat_history)

                    # If entities were found and not in reformulated query, append them
                    if conversation_entities:
                        for entity in conversation_entities:
                            if entity.lower() not in search_query.lower():
                                search_query = f"{search_query} {entity}"
                        logger.debug("Enhanced search query with entities: '%s'", search_query)

                if language == 'en':
                    try:
                        translation = self.openai_client.chat.completions.create(
                            model=self.chat_model,
                            messages=[{
                                "role": "system",
                                "content": "Translate the following English text to Dutch. Return ONLY the translation, nothing else."
                            }, {
                                "role": "user",
                                "content": query
                            }],
                            temperature=0.1
                        )
                        search_query = translation.choices[0].message.content.strip()
                        logger.debug("Translated EN->NL for search: '%s' -> '%s'", query, search_query)
                    except Exception as e:
                        logger.warning("Translation failed, using original query: %s", e)

                # Check cache first
                cached_context = self._get_cached_context(search_query)
                if cached_context:
                    context = cached_context
                else:
                    query_emb = self._get_embedding(search_query)

                    # Feature 13: Fetch more results for diversity filtering
                    results = self.collection.query(query_embeddings=[query_emb], n_results=10)

                    logger.debug("RAG Search Results for '%s':", query)
                    if results["documents"] and results["distances"]:
                        # Feature 13A: Distance Threshold Filtering
                        filtered_docs = []
                        filtered_ids = []
                        filtered_distances = []

                        for i, (doc, doc_id, distance) in enumerate(zip(
                            results["documents"][0],
                            results["ids"][0],
                            results["distances"][0]
                        )):
                            if distance <= self.relevance_threshold:
                                filtered_docs.append(doc)
                                filtered_ids.append(doc_id)
                                filtered_distances.append(distance)
                                logger.debug(
                                    "  Result %d (ID: %s, Distance: %.3f): %s...",
                                    i + 1, doc_id, distance, doc[:100]
                                )
                            else:
                                logger.debug(
                                    "  Filtered out %d (ID: %s, Distance: %.3f > threshold %.2f)",
                                    i + 1, doc_id, distance, self.relevance_threshold
                                )

                        # Feature 13B: Source Diversity - Cap at max 2 chunks per source
                        if filtered_docs:
                            source_count: dict[str, int] = {}
                            diversified_docs = []
                            diversified_ids = []

                            for doc, doc_id in zip(filtered_docs, filtered_ids):
                                # Extract source from document ID (format: "source_chunk_X")
                                source = "_".join(doc_id.split("_")[:-2]) if "_chunk_" in doc_id else doc_id

                                if source_count.get(source, 0) < 2:
                                    diversified_docs.append(doc)
                                    diversified_ids.append(doc_id)
                                    source_count[source] = source_count.get(source, 0) + 1

                                # Take top 5 from diversified set
                                if len(diversified_docs) >= 5:
                                    break

                            logger.debug("After diversity filtering: %d results", len(diversified_docs))
                            context = "\n\n".join(diversified_docs)
                            # Cache the context for future queries
                            if context:
                                self._cache_context(search_query, context)
                        else:
                            logger.debug("  All results filtered out by distance threshold.")
                    else:
                        logger.debug("  No results found.")
            except Exception as e:
                logger.error("RAG Search failed: %s", e)

        if context:
            # Feature 15: Language-aware system instructions
            if language == 'en':
                system_prompt += (
                    f"\nAlways speak on behalf of {brand.name} as a representative. "
                    "Use 'we' and 'our' where appropriate.\n\n"

                    "LANGUAGE & TONE:\n"
                    "- Respond in English\n"
                    "- The knowledge base is in Dutch; translate all information to English\n"
                    "- Write naturally and conversationally\n"
                    "- You are a person in conversation, not a documentation bot\n"
                    "- Keep answers concise (no walls of text)\n\n"

                    "CONVERSATION CONTINUITY (CRITICAL):\n"
                    "- Read the conversation history carefully\n"
                    "- If you discussed a product earlier in this conversation, NEVER deny that\n"
                    "- Check your own previous answers before claiming you don't know something\n"
                    "- If the CONTEXT is now empty but you gave information earlier, "
                    "reference your previous answer: 'As I mentioned earlier...'\n"
                    "- NEVER ask 'which product are we talking about?' if you already know from history\n\n"

                    "CONTEXT & RAG RULES (VERY IMPORTANT):\n"
                    "You operate in a closed world.\n"
                    "- Base your answers exclusively on the provided CONTEXT\n"
                    "- Anything not explicitly in the CONTEXT is considered unknown\n"
                    "- Never invent product names, properties, applications or availability\n"
                    "- Only recommend products whose name appears exactly in the CONTEXT\n"
                    "- Never copy text verbatim from the CONTEXT "
                    "-> always summarize information in your own words\n\n"

                    "INSUFFICIENT OR CONFLICTING INFORMATION:\n"
                    "If the CONTEXT does not contain a direct answer:\n"
                    "- Check if there is related information in the CONTEXT\n"
                    "- Only use it if it logically and explicitly connects\n"
                    "If information in the CONTEXT contradicts itself:\n"
                    "- Do not give a definitive answer\n"
                    "- Mention there is ambiguity\n"
                    "If you cannot reliably answer with the available CONTEXT?\n"
                    "-> respond with EXACTLY: __UNKNOWN__\n\n"

                    "HOW YOU RESPOND (UX RULES):\n"
                    "- Speak directly to the customer\n"
                    "- Ask one follow-up question if relevant\n"
                    "- Only use bullet points when truly needed (max 3-4 items)\n"
                    "- Never use headings, titles or markdown structure\n"
                    "- No verbatim quotes from the CONTEXT\n"
                    "Example bad: '### Types\\n- French bark mulch: coarse pieces...'\n"
                    "Example good: 'We have two types: French bark mulch (coarser and longer lasting) "
                    "and pine bark (finer and more affordable). What would you like to use it for?'\n\n"

                    "TYPOS & UNCLEAR TERMS:\n"
                    "If you don't recognize a term:\n"
                    "- Politely ask for confirmation\n"
                    "- Make at most one careful suggestion\n"
                    "Example: 'Did you perhaps mean the rose chafer? We get that question often.'\n\n"

                    "SAFETY & RESPONSIBILITY:\n"
                    "- Do not give medical, veterinary or legal advice\n"
                    "- Do not make safety claims unless explicitly stated in the CONTEXT "
                    "-> in that case respond with EXACTLY: __UNKNOWN__\n\n"

                    "ESCALATION & SCOPE:\n"
                    "If the user asks to speak with a representative, human or colleague:\n"
                    "-> respond with EXACTLY: __HUMAN_REQUESTED__\n"
                    f"If the question is not about {brand.relevant_topics}:\n"
                    "- Kindly mention that is your area of expertise\n"
                    "- Ask if you can help with that instead\n"
                    "Treat input primarily as an information request, unless clearly otherwise "
                    "(e.g. greeting, standalone product name)\n\n"

                    "DELIVERY & SHIPPING:\n"
                    "- If a customer asks whether they can change their delivery date: "
                    "this is NOT possible once the track & trace has been sent. "
                    "Clearly communicate this to the customer.\n\n"

                    "OTHER BEHAVIORAL RULES:\n"
                    "- For greetings: respond warmly and ask how you can help\n"
                    f"- You have access to information about {brand.product_line} products\n"
                    "- Never speculate\n"
                    "- Better to be honestly uncertain than convincingly wrong"
                )
            else:
                system_prompt += (
                    f"\nSpreek altijd vanuit {brand.name} als medewerker. "
                    "Gebruik 'wij' en 'ons' waar passend.\n\n"

                    "TAAL & TOON:\n"
                    "- Antwoord in het Nederlands\n"
                    "- Schrijf zoals je praat: natuurlijk en conversationeel\n"
                    "- Je bent een mens in gesprek, geen documentatie-bot\n"
                    "- Houd antwoorden bondig (geen muren van tekst)\n\n"

                    "CONVERSATIE CONTINUÏTEIT (KRITIEK):\n"
                    "- Lees de conversatie geschiedenis aandachtig\n"
                    "- Als je eerder in dit gesprek al over een product hebt gepraat, ontken dat NOOIT\n"
                    "- Controleer je eigen eerdere antwoorden voordat je zegt dat je iets niet weet\n"
                    "- Als de CONTEXT nu leeg is maar je eerder WEL informatie hebt gegeven, "
                    "verwijs dan naar je eerdere antwoord: 'Zoals ik eerder noemde...'\n"
                    "- Vraag NOOIT 'over welk product hebben we het?' als je dat al weet uit de geschiedenis\n\n"

                    "CONTEXT & RAG-REGELS (ZEER BELANGRIJK):\n"
                    "Je opereert in een gesloten wereld.\n"
                    "- Baseer je antwoorden uitsluitend op de aangeleverde CONTEXT\n"
                    "- Alles wat niet expliciet in de CONTEXT staat, beschouw je als onbekend\n"
                    "- Verzin nooit productnamen, eigenschappen, toepassingen of beschikbaarheid\n"
                    "- Beveel alleen producten aan waarvan de naam exact in de CONTEXT voorkomt\n"
                    "- Kopieer nooit letterlijk tekst uit de CONTEXT "
                    "-> vat informatie altijd samen in je eigen woorden\n\n"

                    "ONVOLDOENDE OF CONFLICTERENDE INFORMATIE:\n"
                    "Als de CONTEXT geen direct antwoord bevat:\n"
                    "- Kijk of er gerelateerde informatie in de CONTEXT staat\n"
                    "- Gebruik die alleen als het logisch en expliciet aansluit\n"
                    "Als informatie in de CONTEXT elkaar tegenspreekt:\n"
                    "- Geef geen definitief antwoord\n"
                    "- Benoem dat er onduidelijkheid is\n"
                    "Kun je het niet betrouwbaar beantwoorden met de beschikbare CONTEXT?\n"
                    "-> antwoord met PRECIES: __UNKNOWN__\n\n"

                    "HOE JE ANTWOORDT (UX-REGELS):\n"
                    "- Praat direct tegen de klant\n"
                    "- Stel indien zinvol één vervolgvraag\n"
                    "- Gebruik opsommingen alleen als het echt nodig is (max. 3-4 punten)\n"
                    "- Gebruik nooit koppen, titels of markdown-structuur\n"
                    "- Geen letterlijke citaten uit de CONTEXT\n"
                    "Voorbeeld fout: '### Soorten\\n- Franse boomschors: grove stukken...'\n"
                    "Voorbeeld goed: 'We hebben twee soorten: Franse boomschors (grover en gaat langer mee) "
                    "en dennenschors (fijner en wat voordeliger). Waar wil je het voor gebruiken?'\n\n"

                    "TYPEFOUTEN & ONDUIDELIJKE TERMEN:\n"
                    "Herken je een term niet?\n"
                    "- Vraag vriendelijk om bevestiging\n"
                    "- Doe maximaal één voorzichtige suggestie\n"
                    "Voorbeeld: 'Bedoelt u misschien de rozenkever? Dat horen we vaker.'\n\n"

                    "VEILIGHEID & VERANTWOORDELIJKHEID:\n"
                    "- Geef geen medisch, veterinair of juridisch advies\n"
                    "- Doe geen uitspraken over veiligheid als dit niet expliciet in de CONTEXT staat "
                    "-> antwoord in dat geval met PRECIES: __UNKNOWN__\n\n"

                    "ESCALATIE & SCOPE:\n"
                    "Vraagt de gebruiker om contact met een medewerker, mens of collega?\n"
                    "-> antwoord met PRECIES: __HUMAN_REQUESTED__\n"
                    f"Gaat de vraag niet over {brand.relevant_topics}?\n"
                    "- Zeg vriendelijk dat je daarin gespecialiseerd bent\n"
                    "- Vraag of je daarmee kunt helpen\n"
                    "Behandel input primair als een informatieverzoek, tenzij duidelijk anders "
                    "(bijv. begroeting, losse productnaam)\n\n"

                    "BEZORGING & VERZENDING:\n"
                    "- Als een klant vraagt of ze de leveringsdatum kunnen wijzigen: "
                    "dit is NIET mogelijk zodra de track & trace is verzonden. "
                    "Communiceer dit duidelijk aan de klant.\n\n"

                    "OVERIGE GEDRAGSREGELS:\n"
                    "- Bij begroetingen: reageer vriendelijk en vraag hoe je kunt helpen\n"
                    f"- Je hebt toegang tot informatie over {brand.product_line} producten\n"
                    "- Speculeer nooit\n"
                    "- Wees liever eerlijk onzeker dan overtuigend fout"
                )

            # Build conversation summary for assistant awareness
            conversation_summary = ""
            if chat_history:
                # Extract assistant's last 2 statements about products
                assistant_statements = [
                    msg['content'] for msg in chat_history[-6:]
                    if msg['role'] == 'assistant'
                ][-2:]

                if assistant_statements:
                    if language == 'en':
                        conversation_summary = (
                            "\n\nIMPORTANT - Your recent statements in this conversation:\n"
                            + "\n".join(f"- You said: {stmt[:200]}" for stmt in assistant_statements)
                            + "\nDo NOT contradict these statements. Reference them if relevant.\n"
                        )
                    else:
                        conversation_summary = (
                            "\n\nBELANGRIJK - Je recente uitspraken in dit gesprek:\n"
                            + "\n".join(f"- Je zei: {stmt[:200]}" for stmt in assistant_statements)
                            + "\nSpreek dit NIET tegen. Verwijs ernaar waar relevant.\n"
                        )

            user_content = f"Context:\n{context}\n{conversation_summary}\n\nQuestion: {query}"
        elif chat_history:
            # No RAG context available, but we have conversation history.
            # Use conversation history to maintain context instead of returning __UNKNOWN__.
            if language == 'en':
                system_prompt += (
                    "\nYou are a helpful customer service representative. "
                    "The knowledge base is currently unavailable, but you have the conversation history. "
                    "Use the conversation history to maintain context and provide helpful responses.\n\n"
                    "CONVERSATION CONTINUITY (CRITICAL):\n"
                    "- Read the conversation history carefully\n"
                    "- If you discussed a product earlier in this conversation, NEVER deny that\n"
                    "- Check your own previous answers before claiming you don't know something\n"
                    "- Reference your previous answers: 'As I mentioned earlier...'\n"
                    "- NEVER ask 'which product are we talking about?' if you already know from history\n"
                    "- If you gave information earlier, use that to answer follow-up questions\n\n"
                    "If you truly cannot answer, say so honestly but never forget what was already discussed."
                )
            else:
                system_prompt += (
                    "\nJe bent een vriendelijke klantenservice medewerker. "
                    "De kennisbank is momenteel niet beschikbaar, maar je hebt de gespreksgeschiedenis. "
                    "Gebruik de gespreksgeschiedenis om context te behouden en behulpzame antwoorden te geven.\n\n"
                    "CONVERSATIE CONTINUÏTEIT (KRITIEK):\n"
                    "- Lees de conversatie geschiedenis aandachtig\n"
                    "- Als je eerder in dit gesprek al over een product hebt gepraat, ontken dat NOOIT\n"
                    "- Controleer je eigen eerdere antwoorden voordat je zegt dat je iets niet weet\n"
                    "- Verwijs naar je eerdere antwoorden: 'Zoals ik eerder noemde...'\n"
                    "- Vraag NOOIT 'over welk product hebben we het?' als je dat al weet uit de geschiedenis\n"
                    "- Als je eerder informatie hebt gegeven, gebruik die om vervolgvragen te beantwoorden\n\n"
                    "Als je echt niet kunt antwoorden, zeg dat eerlijk maar vergeet nooit wat al besproken is."
                )

            # Build conversation summary for the fallback path too
            conversation_summary = ""
            assistant_statements = [
                msg['content'] for msg in chat_history[-6:]
                if msg['role'] == 'assistant'
            ][-2:]

            if assistant_statements:
                if language == 'en':
                    conversation_summary = (
                        "\n\nIMPORTANT - Your recent statements in this conversation:\n"
                        + "\n".join(f"- You said: {stmt[:200]}" for stmt in assistant_statements)
                        + "\nDo NOT contradict these statements. Reference them if relevant.\n"
                    )
                else:
                    conversation_summary = (
                        "\n\nBELANGRIJK - Je recente uitspraken in dit gesprek:\n"
                        + "\n".join(f"- Je zei: {stmt[:200]}" for stmt in assistant_statements)
                        + "\nSpreek dit NIET tegen. Verwijs ernaar waar relevant.\n"
                    )

            user_content = f"Geen kennisbank context beschikbaar.{conversation_summary}\n\nQuestion: {query}"
        else:
            return "__UNKNOWN__"

        try:
            # Build messages list with system prompt first
            messages: list[dict[str, str]] = [
                {"role": "system", "content": system_prompt}
            ]

            # Add conversation history (last 5 exchanges max to avoid token limits)
            if chat_history:
                # Limit to last 10 messages (5 user + 5 assistant)
                recent_history = chat_history[-10:]
                messages.extend(recent_history)

            # Add current query with context
            messages.append({"role": "user", "content": user_content})

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Error querying OpenAI: %s", e)
            if language == 'en':
                return "Oops, something went wrong on my end! Please try again."
            return "Oeps, er ging even iets mis aan mijn kant! Probeer het nog eens?"

    def extract_name(self, text: str) -> str:
        """Extract a name from user input using LLM."""
        logger.debug("Extracting name from raw input: '%s'", text)

        if not self.openai_client:
            return text

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a specialized Name Extractor. The user is replying to "
                            "'What is your name?'. Output ONLY the name. Remove all filler "
                            "words like 'Yes', 'Please', 'I am', 'My name is', 'Ja', 'Graag', "
                            "'Ik heet'. Example: 'Ja graag, ik heet Wilco' -> 'Wilco'. "
                            "Example: 'Wilco Schouten' -> 'Wilco Schouten'."
                        )
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.0
            )
            extracted = response.choices[0].message.content
            if extracted:
                extracted = extracted.strip()
                logger.debug("Extracted name: '%s'", extracted)
                return extracted
            return text
        except Exception as e:
            logger.error("Error extracting name: %s", e)
            return text

    def detect_ticket_intent(self, text: str) -> str:
        """Detect user intent during ticket creation flow.

        When the bot asks for the user's name to create a support ticket,
        this function classifies what the user actually wants:
        - 'giving_name': User is providing their name
        - 'declining': User doesn't want a ticket/help
        - 'new_question': User is asking something else entirely

        Args:
            text: The user's response

        Returns:
            One of: 'giving_name', 'declining', 'new_question'
        """
        # Quick keyword check for obvious declines (Dutch & English)
        # This catches common phrases even if LLM fails
        text_lower = text.lower().strip()
        decline_keywords = [
            'nee', 'laat maar', 'no', 'never mind', 'forget it',
            'niet nodig', 'hoeft niet', 'no thanks', 'nope', 'nee hoor',
            'laat maar zitten', 'geen interesse', 'not interested'
        ]
        for phrase in decline_keywords:
            if phrase in text_lower:
                logger.debug("Keyword match for declining: '%s' in '%s'", phrase, text[:50])
                return 'declining'

        if not self.openai_client:
            return 'giving_name'  # Default to assuming they gave their name

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You classify user responses during a support ticket flow. "
                            "The bot just asked: 'Want me to get a colleague to help? What's your name?'\n\n"
                            "Classify the user's response as ONE of:\n"
                            "- giving_name: User provides their name (e.g., 'Jan', 'Mijn naam is Wilco', 'Wilco Schouten')\n"
                            "- declining: User declines help (e.g., 'Nee', 'Nee ik wil niet', 'Laat maar', 'No thanks')\n"
                            "- new_question: User asks something unrelated (e.g., 'Wat kost product X?', 'How do I...')\n\n"
                            "Output ONLY one word: giving_name, declining, or new_question"
                        )
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.0,
                max_completion_tokens=10
            )
            result = response.choices[0].message.content
            if result:
                result = result.strip().lower()
                if result in ('giving_name', 'declining', 'new_question'):
                    logger.debug("Detected ticket intent '%s' for: %s", result, text[:50])
                    return result
            return 'giving_name'  # Default
        except Exception as e:
            logger.error("Error detecting ticket intent: %s", e)
            return 'giving_name'

    def detect_language(self, text: str) -> str:
        """Detect if text is Dutch or English using LLM.

        Args:
            text: The text to analyze

        Returns:
            'nl' for Dutch, 'en' for English
        """
        if not self.openai_client:
            return 'en'  # Default to English

        # Short texts might be ambiguous, default to Dutch for this Dutch company
        if len(text.strip()) < 5:
            return 'nl'

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a language detector. Analyze the user's message and "
                            "respond with ONLY 'nl' if it's Dutch, or 'en' if it's English. "
                            "If uncertain, respond 'nl' (Dutch is the default). "
                            "Output nothing else, just the 2-letter code."
                        )
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.0,
                max_completion_tokens=5
            )
            result = response.choices[0].message.content
            if result:
                result = result.strip().lower()
                if result in ('nl', 'en'):
                    logger.debug("Detected language '%s' for: %s", result, text[:50])
                    return result
            return 'nl'  # Default to Dutch
        except Exception as e:
            logger.error("Error detecting language: %s", e)
            return 'nl'  # Default to Dutch on error

    def generate_helpful_unknown_response(self, question: str, language: str = 'nl') -> str:
        """Generate a helpful response when we don't have specific info.

        Instead of immediately offering human handoff, this generates a response that:
        1. Acknowledges what the user asked
        2. Explains what we know related to the topic
        3. Asks a clarifying question or offers alternative help

        Args:
            question: The user's original question
            language: 'nl' for Dutch, 'en' for English

        Returns:
            A helpful response string
        """
        if not self.openai_client:
            # Fallback if no client
            if language == 'nl':
                return (
                    "Hmm, daar heb ik helaas geen specifieke informatie over. "
                    "Kan ik je ergens anders mee helpen, of wil je dat ik een collega vraag?"
                )
            return (
                "Hmm, I don't have specific information about that. "
                "Can I help you with something else, or would you like me to ask a colleague?"
            )

        try:
            if language == 'nl':
                system_prompt = (
                    "Je bent een vriendelijke klantenservice medewerker. "
                    "De klant stelde een vraag waar je geen specifiek antwoord op hebt. "
                    "Genereer een korte, behulpzame reactie die:\n"
                    "1. Erkent dat je die specifieke info niet hebt\n"
                    "2. Iets nuttigs deelt als je dat wel weet (algemene info over het onderwerp)\n"
                    "3. Een vervolgvraag stelt of alternatieven biedt\n"
                    "4. NIET direct een collega of menselijke hulp aanbiedt - dat is laatste optie\n\n"
                    "Houd het kort (2-3 zinnen max). Wees conversationeel, niet formeel."
                )
            else:
                system_prompt = (
                    "You are a friendly customer service agent. "
                    "The customer asked a question you don't have specific info for. "
                    "Generate a short, helpful response that:\n"
                    "1. Acknowledges you don't have that specific info\n"
                    "2. Shares something useful if you know related info\n"
                    "3. Asks a follow-up question or offers alternatives\n"
                    "4. Does NOT immediately offer human help - that's a last resort\n\n"
                    "Keep it brief (2-3 sentences max). Be conversational, not formal."
                )

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Klant vraagt: {question}"}
                ],
                temperature=0.7,
                max_completion_tokens=150
            )
            result = response.choices[0].message.content
            if result:
                return result.strip()
        except Exception as e:
            logger.error("Error generating helpful unknown response: %s", e)

        # Fallback
        if language == 'nl':
            return (
                "Hmm, daar heb ik helaas geen specifieke informatie over. "
                "Kan ik je ergens anders mee helpen?"
            )
        return (
            "Hmm, I don't have specific information about that. "
            "Can I help you with something else?"
        )
