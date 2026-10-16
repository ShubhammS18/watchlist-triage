"""The evaluation harness for task T06 (FR-20, NFR-3, NFR-6). Python standard library only.

`run.run` is the run step: it shows an agent every alert and control twin of a world in three framings, one
bundle per call, and writes the outputs, the manifest and the run-set index (`manifest`). It never imports
worldgen.truth and never opens a world's hidden folder; scoring is a separate step. See docs/harness-design.md.
"""
