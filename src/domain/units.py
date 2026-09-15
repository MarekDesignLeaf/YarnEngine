"""Exact canonical unit conversions."""
from math import ceil
def tex_from_metres_per_100g(m):
    if m <= 0: raise ValueError("m must be > 0")
    return 100000.0/m
def metres_per_100g_from_tex(tex):
    if tex <= 0: raise ValueError("tex must be > 0")
    return 100000.0/tex
def mass_g_from_length_m(length_m, tex):
    if length_m < 0 or tex <= 0: raise ValueError("invalid input")
    return length_m*tex/1000.0
def packages_required(length_m, package_length_m):
    if length_m < 0 or package_length_m <= 0: raise ValueError("invalid input")
    return ceil(length_m/package_length_m)
