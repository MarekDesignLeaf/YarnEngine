# Real Swatch Calibration Protocol v0.1

## Objective
Create calibration records whose measurement conditions are explicit enough that repeatability and reproducibility can be assessed.

## Required per swatch
* unique record ID
* replicate group ID
* knitter ID
* exact pattern version
* yarn ID and available label/linear-density evidence
* needle size
* gauge counts over an explicit physical width and height
* project/pattern operation counts
* measured yarn length for the defined swatch core
* swatch condition: unblocked, blocked, washed, relaxed or unknown
* operator, date, method and instrument/evidence references

## Replicates
For calibration-quality measurements, target at least 3 independent swatches per replicate group where practical.
This is a project protocol choice, not a universal knitting standard.
The software reports sample standard deviation and coefficient of variation and flags groups below the configured replicate count.

## Isolation
The measured yarn length must correspond to the same defined fabric region as the operation counts.
Cast-on, bind-off, tails and unrelated borders must either be excluded or represented as explicit operations.

## Validation
Do not validate by randomly mixing multiple swatches from the same knitter/yarn/pattern condition across train and test.
Use grouped validation to answer harder questions such as:
* generalisation to a new knitter
* generalisation to a new yarn
* generalisation to a new pattern

This follows the statistical principle that repeated/related observations should not leak across train and test groups.
