from dataclasses import dataclass
from collections import defaultdict

@dataclass
class LibraryRegistry:
    yarns:dict
    patterns:dict
    pattern_metadata:dict

    @classmethod
    def empty(cls): return cls({}, {}, {})

    def add_yarn(self,yarn):
        if yarn.yarn_id in self.yarns: raise ValueError(f"duplicate yarn_id {yarn.yarn_id}")
        self.yarns[yarn.yarn_id]=yarn

    def add_pattern(self,pattern,metadata):
        key=(pattern.pattern_id,pattern.version)
        if key in self.patterns: raise ValueError(f"duplicate pattern version {key}")
        if metadata.pattern_id!=pattern.pattern_id or metadata.version!=pattern.version:
            raise ValueError("metadata identity mismatch")
        self.patterns[key]=pattern
        self.pattern_metadata[key]=metadata

    def latest_pattern(self,pattern_id):
        versions=[k for k in self.patterns if k[0]==pattern_id]
        if not versions: raise KeyError(pattern_id)
        # semantic-ish numeric sort, adequate for x.y.z versions
        def vk(k):
            try: return tuple(int(x) for x in k[1].split("."))
            except: return (0,)
        return self.patterns[max(versions,key=vk)]
