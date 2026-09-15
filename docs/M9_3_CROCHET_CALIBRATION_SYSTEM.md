# M9.3 Crochet Calibration System

M9.3 creates a separate evidence path for crochet and amigurumi rather than reusing knitting calibration assumptions.

A crochet calibration record captures:
crocheter, yarn, hook size, measured gauge, construction type (flat/round/spiral), exact canonical crochet operation counts, measured yarn length, optional mass/tex/diameter, replicate group and evidence reference.

Core amigurumi evidence coverage currently tracks SC, SC_INC, SC2TOG, SC_BLO, SC_FLO, SLST and CH.

Readiness gates are configurable project protocol gates. Defaults require three measured records per required operation and three measurements in every included replicate group. These defaults are not claimed as universal scientific thresholds.

A crochet-specific fitting adapter is included and uses the existing calibration model machinery while retaining model_scope=crochet.

No synthetic crochet coefficients or fake production calibration records are bundled. The supplied JSON is a blank measurement template only.
