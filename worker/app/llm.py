"""Optional LLM justification for ambiguous candidates.

The LLM never makes the primary decision; it only adds a structured reason for
candidates already classified as NEAR_DUPLICATE or SEMANTICALLY_RELATED. If no
LLM_API_KEY is configured, every call is a no-op and the deterministic reason
is kept.
"""
import json
import logging

from app import config

log = logging.getLogger("worker.llm")

_PROMPT = """Você é um assistente jurídico. Compare os trechos do DOCUMENTO NOVO com os do DOCUMENTO CANDIDATO e os scores calculados. Responda APENAS com um JSON válido no formato:
{{"classification": "NEAR_DUPLICATE|SEMANTICALLY_RELATED", "reason": "texto curto", "changed_elements": ["..."]}}

Classificação determinística sugerida: {classification}
Scores: near_duplicate_score={near}, semantic_score={semantic}

DOCUMENTO NOVO (trechos relevantes):
{source_chunks}

DOCUMENTO CANDIDATO (trechos correspondentes):
{matched_chunks}
"""


def justify(classification, near_score, semantic_score, evidence):
    """Return a dict {reason, changed_elements} or None when disabled/failed."""
    if not config.LLM_ENABLED:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
        source_chunks = "\n---\n".join(e["source_chunk"] for e in evidence)
        matched_chunks = "\n---\n".join(e["matched_chunk"] for e in evidence)
        prompt = _PROMPT.format(
            classification=classification,
            near=round(near_score, 3),
            semantic=round(semantic_score, 3),
            source_chunks=source_chunks,
            matched_chunks=matched_chunks,
        )
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return {
            "reason": data.get("reason"),
            "changed_elements": data.get("changed_elements", []),
        }
    except Exception as exc:  # never let the LLM break the deterministic pipeline
        log.warning("LLM justification failed, keeping deterministic reason: %s", exc)
        return None
