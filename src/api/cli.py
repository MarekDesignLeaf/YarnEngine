import argparse, json
from src.gauge_engine.gauge import Gauge
from src.calibration.swatch import CoreSwatchCalibration
from src.consumption.engine import calculate_from_swatch, calculate_plain_geometry

def main():
    p=argparse.ArgumentParser(description="Yarn Consumption Engine M1")
    sp=p.add_subparsers(dest="mode",required=True)

    a=sp.add_parser("swatch")
    for x in ("width","height","gauge_width","gauge_height"): a.add_argument(f"--{x}",type=float,required=True)
    for x in ("gauge_stitches","gauge_rows","swatch_stitches","swatch_rows"): a.add_argument(f"--{x}",type=int,required=True)
    a.add_argument("--swatch_length",type=float,required=True)
    a.add_argument("--allowance",type=float,default=0)
    a.add_argument("--tex",type=float)
    a.add_argument("--package_length",type=float)

    b=sp.add_parser("geometry")
    for x in ("width","height","gauge_width","gauge_height","yarn_diameter"): b.add_argument(f"--{x}",type=float,required=True)
    for x in ("gauge_stitches","gauge_rows"): b.add_argument(f"--{x}",type=int,required=True)
    b.add_argument("--allowance",type=float,default=0)
    b.add_argument("--tex",type=float)
    b.add_argument("--package_length",type=float)

    x=p.parse_args()
    gauge=Gauge(x.gauge_stitches,x.gauge_rows,x.gauge_width,x.gauge_height)
    common=dict(width_mm=x.width,height_mm=x.height,gauge=gauge,allowance_percent=x.allowance,tex=x.tex,package_length_m=x.package_length)
    if x.mode=="swatch":
        cal=CoreSwatchCalibration(x.swatch_stitches,x.swatch_rows,x.swatch_length)
        result=calculate_from_swatch(calibration=cal,**common)
    else:
        result=calculate_plain_geometry(yarn_diameter_mm=x.yarn_diameter,**common)
    print(json.dumps(result.to_dict(),indent=2))

if __name__=="__main__": main()
