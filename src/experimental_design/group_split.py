from collections import defaultdict

def leave_one_group_out(records, group_field: str):
    groups=defaultdict(list)
    for i,r in enumerate(records):
        groups[getattr(r,group_field)].append(i)
    if len(groups)<2:
        raise ValueError("at least two distinct groups required")
    folds=[]
    all_idx=set(range(len(records)))
    for group,idx in sorted(groups.items(),key=lambda kv:str(kv[0])):
        test=tuple(idx)
        train=tuple(sorted(all_idx-set(idx)))
        folds.append({"group":group,"train_indices":train,"test_indices":test})
    return tuple(folds)

def grouped_holdout(records, group_field: str, test_fraction=0.2):
    if not (0<test_fraction<1): raise ValueError("test_fraction must be in (0,1)")
    groups=sorted({getattr(r,group_field) for r in records},key=str)
    if len(groups)<2: raise ValueError("at least two groups required")
    n_test=max(1,round(len(groups)*test_fraction))
    test_groups=set(groups[-n_test:])
    train=[]; test=[]
    for i,r in enumerate(records):
        (test if getattr(r,group_field) in test_groups else train).append(i)
    if not train or not test: raise ValueError("empty split")
    return {"group_field":group_field,"test_groups":tuple(sorted(test_groups,key=str)),
            "train_indices":tuple(train),"test_indices":tuple(test)}
