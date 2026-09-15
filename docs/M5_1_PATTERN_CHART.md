# M5.1 Graphical Pattern Chart

M5.1 adds a chart renderer derived directly from the canonical machine-readable pattern definition.

## Design rules

* The executable pattern is the single source of truth.
* No separate hand-authored picture is stored.
* A multi-stitch operation spans the correct number of produced fabric columns.
* The repeat width and repeat height are visible.
* Row number, RS/WS side and knitting direction are explicit.
* The legend is generated from the operation registry.
* The renderer uses YCE application-native symbols; operation IDs remain canonical semantics.
* Rows are displayed highest-first for chart viewing, while the row's stored operation sequence is preserved.

## Why produced-stitch geometry

Knitting charts represent the fabric produced by each row. This matters for balanced lace: `YO` produces a stitch without consuming one, while `K2TOG` consumes two and produces one. Using produced stitch count allows a balanced row to render to the declared repeat width.

## Safety

If rendered row width differs from the declared repeat width, the API returns a warning instead of silently stretching the chart.

## Endpoint

`GET /api/patterns/{pattern_id}/{version}/chart`

The endpoint returns row/cell spans and a legend. The browser renders this as a responsive CSS grid and supports an expanded chart view.
