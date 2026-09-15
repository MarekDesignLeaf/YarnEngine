from dataclasses import dataclass

@dataclass(frozen=True)
class CoreSwatchCalibration:
    """Measured yarn consumption for a defined central fabric region.

    The length must refer to the same fabric core represented by stitches × rows.
    Cast-on, bind-off, tails and unrelated border yarn must be excluded.
    """
    stitches: int
    rows: int
    yarn_length_m: float

    def __post_init__(self):
        if self.stitches <= 0 or self.rows <= 0 or self.yarn_length_m <= 0:
            raise ValueError("swatch stitches, rows and yarn length must be > 0")

    @property
    def stitch_positions(self) -> int:
        return self.stitches * self.rows

    @property
    def metres_per_stitch_position(self) -> float:
        return self.yarn_length_m / self.stitch_positions

    def predict_core_length_m(self, project_stitches: int, project_rows: int) -> float:
        if project_stitches <= 0 or project_rows <= 0:
            raise ValueError("project stitches and rows must be > 0")
        return self.metres_per_stitch_position * project_stitches * project_rows
