# Data kept in the repo

`esmis-wpc-reports.txt`: the path of every weekly WPC report that USDA's ESMIS archive listed on 21 October
2026 (352 files, November 2018 to October 2026). The archive lists only its latest reports, so the oldest drop
off the listing as new ones arrive, but the files stay online. `src/protein/usda.py` reads these as well as the
live listing, so a fresh download still starts in November 2018.

`dmn-wpc80-isolate-2026.csv`: USDA Dairy Market News quotes WPC 80% and whey protein isolate only in words, in
the text of its weekly WPC report (report 1053, Central and West US). Each row is one report (its Thursday release
date), the phrase as written, and the price range it implies in $/lb:
- "low $Xs" is X.00 to X.40, "mid-$Xs" is X.40 to X.60, "upper $Xs" is X.60 to X.99, and "$Xs" is X.00 to X.99
  (written as X+1.00).
- "about" or "near" a price is that price.

The phrases were read from the reports twice, independently, on 21 Oct 2026. Where both readings cover the same
week they agree: mid-August (WPC 80% $12 to $13, isolate about $14), early October (low $10s to
mid-$11s; $14s) and 15 October (mostly $9s; mostly $14s). Sources: `https://www.ams.usda.gov/mnreports/ams_1053.pdf` (latest) and
the weekly PDFs mirrored at `https://www.clal.it/upload/<date>-ams_1053.pdf`. There is no earlier dollar quote:
DMN mentioned WPC 80% and isolate only in words before 28 May 2026.
