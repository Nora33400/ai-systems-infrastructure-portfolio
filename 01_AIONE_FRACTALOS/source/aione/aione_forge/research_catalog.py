from __future__ import annotations

EXTERNAL_SOURCES = [
    {
        "id": "EXT-REACT",
        "title": "ReAct",
        "url": "https://arxiv.org/abs/2210.03629",
        "use": "Interleave reasoning, actions, observations, and plan updates.",
    },
    {
        "id": "EXT-REFLEXION",
        "title": "Reflexion",
        "url": "https://arxiv.org/abs/2303.11366",
        "use": "Use verbal feedback and episodic memory instead of model fine-tuning.",
    },
    {
        "id": "EXT-VOYAGER",
        "title": "Voyager",
        "url": "https://arxiv.org/abs/2305.16291",
        "use": "Maintain an automatic curriculum and reusable skill library.",
    },
    {
        "id": "EXT-SELF-RAG",
        "title": "Self-RAG",
        "url": "https://arxiv.org/abs/2310.11511",
        "use": "Retrieve, generate, critique, and decide when evidence is needed.",
    },
    {
        "id": "EXT-TOT",
        "title": "Tree of Thoughts",
        "url": "https://arxiv.org/abs/2305.10601",
        "use": "Explore branches, self-evaluate, and backtrack for hard tasks.",
    },
    {
        "id": "EXT-GOT",
        "title": "Graph of Thoughts",
        "url": "https://arxiv.org/abs/2308.09687",
        "use": "Represent reasoning as a graph with feedback and distillation.",
    },
    {
        "id": "EXT-TOOLFORMER",
        "title": "Toolformer",
        "url": "https://arxiv.org/abs/2302.04761",
        "use": "Score and learn useful tool calls.",
    },
    {
        "id": "EXT-AUTOGEN-PAPER",
        "title": "AutoGen paper",
        "url": "https://arxiv.org/abs/2308.08155",
        "use": "Coordinate specialist agents via structured conversation.",
    },
]


GITHUB_CANDIDATES = [
    {
        "id": "GH-LANGGRAPH",
        "name": "langchain-ai/langgraph",
        "url": "https://github.com/langchain-ai/langgraph",
        "candidate_for": "durable stateful agent graphs",
    },
    {
        "id": "GH-AUTOGEN",
        "name": "microsoft/autogen",
        "url": "https://github.com/microsoft/autogen",
        "candidate_for": "multi-agent conversation runtime",
    },
    {
        "id": "GH-CREWAI",
        "name": "crewAIInc/crewAI",
        "url": "https://github.com/crewAIInc/crewAI",
        "candidate_for": "role-based agent crews",
    },
    {
        "id": "GH-LLAMA-INDEX",
        "name": "run-llama/llama_index",
        "url": "https://github.com/run-llama/llama_index",
        "candidate_for": "RAG, document agents, ingestion, OCR",
    },
    {
        "id": "GH-HAYSTACK",
        "name": "deepset-ai/haystack",
        "url": "https://github.com/deepset-ai/haystack",
        "candidate_for": "modular RAG and LLM pipelines",
    },
    {
        "id": "GH-CHATRTX",
        "name": "NVIDIA/ChatRTX",
        "url": "https://github.com/NVIDIA/ChatRTX",
        "candidate_for": "Windows local RTX RAG reference",
    },
]


NVIDIA_MODEL_ROLES = [
    {
        "role": "planner_deep",
        "candidate_models": [
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/nemotron-3-super-120b-a12b",
        ],
        "selection_reason": "Deep planning and architecture synthesis.",
        "availability_checked_at": None,
        "fallback_role": "fast_router_or_summarizer",
        "cost_class": "high",
        "local_available": False,
        "remote_available": True,
        "notes": "Use only after current availability and free endpoint status are verified.",
    },
    {
        "role": "fast_router_or_summarizer",
        "candidate_models": [
            "nvidia/llama-3.1-nemotron-nano-8b-v1",
            "nvidia/nemotron-mini-4b-instruct",
            "nvidia/nvidia-nemotron-nano-9b-v2",
        ],
        "selection_reason": "Low-cost routing, summaries, checklist passes, and simple classification.",
        "availability_checked_at": None,
        "fallback_role": None,
        "cost_class": "low",
        "local_available": False,
        "remote_available": True,
        "notes": "For low-cost routing, summaries, and checklist passes.",
    },
    {
        "role": "safety",
        "candidate_models": [
            "nvidia/nemotron-3-content-safety",
            "nvidia/llama-3.1-nemoguard-8b-content-safety",
            "nvidia/nemoguard-jailbreak-detect",
        ],
        "selection_reason": "Safety gates before tool execution, network actions, or file mutations.",
        "availability_checked_at": None,
        "fallback_role": None,
        "cost_class": "medium",
        "local_available": False,
        "remote_available": True,
        "notes": "Use as SafetyGate before tool execution or external actions.",
    },
    {
        "role": "retrieval_rerank",
        "candidate_models": [
            "nvidia/llama-nemotron-rerank-1b-v2",
            "nvidia/llama-nemotron-rerank-vl-1b-v2",
        ],
        "selection_reason": "Evidence ranking, source selection, and claim grounding.",
        "availability_checked_at": None,
        "fallback_role": "fast_router_or_summarizer",
        "cost_class": "low",
        "local_available": False,
        "remote_available": True,
        "notes": "Use for source ranking and claim evidence selection.",
    },
    {
        "role": "ocr_document",
        "candidate_models": [
            "nvidia/nemotron-ocr-v1",
        ],
        "selection_reason": "OCR for PDFs or image documents when local extraction fails.",
        "availability_checked_at": None,
        "fallback_role": None,
        "cost_class": "medium",
        "local_available": False,
        "remote_available": True,
        "notes": "Use for local PDF/images that pypdf cannot extract.",
    },
    {
        "role": "code",
        "candidate_models": [
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        ],
        "selection_reason": "Code generation and patch proposal after planning and verification.",
        "availability_checked_at": None,
        "fallback_role": "planner_deep",
        "cost_class": "high",
        "local_available": False,
        "remote_available": True,
        "notes": "Use only for scoped code increments with tests and patch ledger.",
    },
    {
        "role": "embedding",
        "candidate_models": [
            "nvidia/llama-3.2-nv-embedqa-1b-v2",
            "nvidia/nv-embedqa-e5-v5",
        ],
        "selection_reason": "Vector search, memory retrieval, and source similarity.",
        "availability_checked_at": None,
        "fallback_role": "retrieval_rerank",
        "cost_class": "low",
        "local_available": False,
        "remote_available": True,
        "notes": "Verify current endpoint availability before use.",
    },
]
