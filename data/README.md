# Hand-entered data

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
