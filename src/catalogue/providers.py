"""Provider-independent generation contracts for Catalogue Factory.

Generation providers can create candidates. They never validate, approve, lock,
publish, or mutate an existing approved binary.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Protocol, Any


@dataclass(frozen=True)
class GenerationRequest:
    task: str
    product_line_id: int
    source_record_version: str
    prompt: str
    references: tuple[dict, ...] = ()
    parameters: dict = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return sha256(self.prompt.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GenerationResult:
    provider_id: str
    model_id: str
    candidate_uri: str | None
    candidate_sha256: str
    metadata: dict = field(default_factory=dict)


class GenerationProvider(Protocol):
    provider_id: str
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, GenerationProvider] = {}

    def register(self, provider: GenerationProvider):
        pid=str(getattr(provider,"provider_id","") or "").strip()
        if not pid: raise ValueError("provider_id is required")
        self._providers[pid]=provider

    def get(self, provider_id: str) -> GenerationProvider:
        try:return self._providers[provider_id]
        except KeyError:raise KeyError("generation provider is not registered")

    def list(self):
        return sorted(self._providers)


class DeterministicFixtureProvider:
    """Test/development provider. It proves the provider boundary without AI."""
    provider_id="fixture"

    def __init__(self, model_id="fixture-v1"):
        self.model_id=model_id

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload=json.dumps({
          "task":request.task,"product_line_id":request.product_line_id,
          "source_record_version":request.source_record_version,
          "prompt_hash":request.prompt_hash,"parameters":request.parameters,
          "references":request.references
        },sort_keys=True,separators=(",",":")).encode("utf-8")
        digest=sha256(payload).hexdigest()
        return GenerationResult(self.provider_id,self.model_id,None,digest,{
          "fixture":True,"payload_sha256":digest
        })


def provenance(request: GenerationRequest, result: GenerationResult) -> dict:
    return {
      "provider_id":result.provider_id,"model_id":result.model_id,
      "prompt_hash":request.prompt_hash,"parameters":request.parameters,
      "reference_count":len(request.references)
    }
