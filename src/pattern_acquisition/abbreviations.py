
from dataclasses import dataclass

@dataclass(frozen=True)
class Abbreviation:
    token: str
    operation_id: str
    confidence: str = "exact"

# Conservative mapping only. Every target must already exist in the operation registry.
# Variants are spelling/case forms, not semantic guesses.
ABBREVIATIONS = {
    "K":"K","KNIT":"K",
    "P":"P","PURL":"P",
    "YO":"YO","YRN":"YO","YFWD":"YO",
    "K2TOG":"K2TOG",
    "P2TOG":"P2TOG",
    "SSK":"SSK",
    "SSP":"SSP",
    "KFB":"KFB",
    "M1L":"M1L",
    "M1R":"M1R",
    "SL1WYIB":"SL1_WYIB","SL1 WYIB":"SL1_WYIB","SL1-WYIB":"SL1_WYIB",
    "SL1WYIF":"SL1_WYIF","SL1 WYIF":"SL1_WYIF","SL1-WYIF":"SL1_WYIF",
    "K3TOG":"K3TOG",
    "P3TOG":"P3TOG",
    "S2KP2":"S2KP2",
    "KTBL":"K_TBL","K TBL":"K_TBL",
    "PTBL":"P_TBL","P TBL":"P_TBL",
    "BO":"BO","BIND OFF":"BO",
    "CO":"CO","CAST ON":"CO",
    "C1/1R":"C1_1R","C1/1L":"C1_1L",
    "C1/1RP":"C1_1RP","C1/1LP":"C1_1LP",
    "C2/1R":"C2_1R","C2/1L":"C2_1L",
    "C2/2R":"C2_2R","C2/2L":"C2_2L",
    "C2/2RP":"C2_2RP","C2/2LP":"C2_2LP",
    "BOBBLE":"BOBBLE",
}
