# M5.2 Interactive Pattern Editor

The web application can now edit a repeat visually.

## Workflow
1. Open an existing canonical pattern.
2. Click **Edit pattern**.
3. Select an operation from the operation palette.
4. Click a chart position to paint the operation.
5. Adjust repeat width/height if required.
6. Validate.
7. Save as a new pattern ID/version.

## Safety and data integrity
The editor does not overwrite the source pattern.
Save creates a new versioned JSON pattern.
Grid validation runs before canonical pattern validation.
Unknown operations, gaps, overlaps, span mismatches and repeat-boundary overflow are rejected.

## Single source of truth
The visual editor produces the same canonical pattern structure consumed by the Pattern Engine.
There is no separate drawing-only pattern representation.

## Current limitation
The editor is repeat-grid based. It does not yet support garment shaping, conditional instructions, colourwork strands or freeform chart annotations.
