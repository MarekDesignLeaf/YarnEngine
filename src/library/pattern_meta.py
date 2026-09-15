from dataclasses import dataclass

@dataclass(frozen=True)
class PatternMetadata:
    pattern_id:str
    version:str
    name:str
    family_id:str
    tags:tuple[str,...]
    difficulty:str
    techniques:tuple[str,...]
    source_type:str
    source_reference:str|None=None
    license_id:str|None=None
    active:bool=True

    def __post_init__(self):
        if not self.pattern_id or not self.version or not self.name or not self.family_id:
            raise ValueError("required pattern metadata missing")
        if self.difficulty not in {"basic","easy","intermediate","experienced","unknown"}:
            raise ValueError("invalid difficulty")
